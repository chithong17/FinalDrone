"""Bounded delivery worker. Original BTC client is imported without edits."""
import asyncio
import importlib.util
import json
import math
import queue
import threading
import time
import uuid
from pathlib import Path

from .contracts import TelemetrySample

_spec = importlib.util.spec_from_file_location('btc_indoor_client', Path(__file__).resolve().parents[1] / 'starter-kit-indoor/indoor_client.py')
btc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(btc)


def get_path(obj, path):
    if not path:
        raise ValueError('Configure the verified response JSON path first')
    for part in path.split('.'):
        obj = obj[part]
    return obj


def normalized_live_sample(raw):
    """Accept normalized dashboard schema only; validate against real status first."""
    stamp = raw.get('t_server')
    if type(stamp) not in (float, int) or not 1e12 < stamp < 1e14:
        raise ValueError('Expected telemetry.t_server epoch milliseconds')
    for key in ('alt_rel', 'yaw'):
        value = raw.get(key)
        if value is not None and (type(value) not in (float, int) or not math.isfinite(value)):
            raise ValueError(f'Invalid telemetry {key}')
    return TelemetrySample(video_time_s=stamp/1000, sample_time_ms=round(stamp),
        alt_rel=raw.get('alt_rel'), aircraft_yaw=raw.get('yaw'),
        gimbal_yaw=raw.get('gimbal_yaw'), gimbal_pitch=raw.get('gimbal_pitch'),
        zoom_factor=raw.get('zoom_factor'), source=raw.get('source', 'status'))


def status_telemetry(status, path):
    """Find a unique normalized OSD object, without assuming its wrapper name.

    Only the exact dashboard fields are recognized. Never use poll time as
    telemetry time, or infer values from unrelated status/session fields.
    """
    if path != 'auto':
        raw = get_path(status, path)
        return normalized_live_sample(raw) if raw is not None else None
    matches = []
    def visit(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            if {'t_server', 'alt_rel', 'yaw'} <= node.keys():
                matches.append(normalized_live_sample(node))
                return
            for value in node.values():
                visit(value, depth+1)
        # Arrays can contain historical records. Do not mistake them for latest OSD.
    visit(status)
    if len(matches) > 1:
        raise ValueError('Ambiguous status telemetry; set explicit JSON path')
    return matches[0] if matches else None


class Delivery:
    def __init__(self, config, server, session, output, timeline):
        self.config, self.server, self.session, self.timeline = config, server, session, timeline
        self.output = Path(output)
        self.outbox = self.output / 'outbox'
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.queue = queue.Queue(maxsize=config['queue_capacity'])
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.deadline = 0
        self.state = 'UNKNOWN'
        self.log_path = self.output / 'delivery.jsonl'
        self.pending_tracks = {}

    def _log(self, event, **fields):
        with self.log_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(event=event, at_ms=int(time.time()*1000), **fields))+'\n')

    def enqueue(self, frame, detection, read, location, track_id):
        kind = self.config['object_type_map'].get(detection.object_type)
        if kind not in {'chair_orange', 'chair_white', 'chair_gray', 'backpack', 'fire_extinguisher'}:
            self._log('rejected', reason='unmapped_object_type', object_type=detection.object_type)
            return False
        if self.state != 'RUNNING' or time.monotonic() >= self.deadline:
            return False
        if track_id in self.pending_tracks:
            path, packet = self.pending_tracks[track_id]
        else:
            packet = btc.make_packet(jpeg=frame.jpeg, session_id=self.session, submission_id=uuid.uuid4().hex,
                target_id=f'track-{track_id}', frame_id=frame.frame_id, captured_at_ms=frame.captured_at_ms,
                object_type=kind, number=read.number, floor=location.floor, direction=location.direction, bbox=detection.bbox)
            path = self.outbox / (packet['submission_id']+'.json')
            btc.save_outbox(path, packet)
        try:
            self.queue.put_nowait((path, packet))
            self.pending_tracks.pop(track_id, None)
            return True
        except queue.Full:
            self.pending_tracks[track_id] = (path, packet)
            self._log('pending', submission_id=packet['submission_id'], reason='queue_full_outbox_preserved')
            return False

    async def _status(self, client):
        state = await client.status(self.session)
        self.state = get_path(state, self.config['status_state_path'])
        remaining = get_path(state, self.config['status_time_left_path'])
        if type(remaining) not in (int, float) or not 0 <= remaining <= 300:
            raise ValueError('Invalid server time_left_s')
        # Never extend the locally established deadline on a later status read.
        limit = time.monotonic()+remaining
        self.deadline = min(self.deadline, limit) if self.deadline else limit
        try:
            sample = status_telemetry(state, self.config['status_telemetry_path'])
        except (ValueError, KeyError, TypeError):
            self._log('telemetry_unavailable', reason='invalid_or_ambiguous_schema')
            return state
        if sample is not None:
            self.timeline.add(sample)
        else:
            self._log('telemetry_unavailable', reason='normalized_osd_missing')
        return state

    async def _poll(self, client):
        while not self.stop.is_set() and time.monotonic() < self.deadline:
            try:
                await self._status(client)
            except Exception as error:
                self._log('telemetry_error', error_type=type(error).__name__)
            await asyncio.sleep(self.config['poll_interval_s'])

    async def _run(self):
        async with btc.IndoorClient(self.server) as client:
            await self._status(client)
            if self.state != 'RUNNING':
                raise ValueError('Round is not RUNNING')
            self.ready.set()
            poll = asyncio.create_task(self._poll(client))
            try:
                while time.monotonic() < self.deadline and (not self.stop.is_set() or not self.queue.empty()):
                    try:
                        path, packet = self.queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(.05)
                        continue
                    try:
                        while time.monotonic() < self.deadline:
                            try:
                                ack = await client.submit(packet)
                                path.with_suffix('.ack.json').write_text(json.dumps(ack), encoding='utf-8')
                                self._log('ack', submission_id=packet['submission_id'])
                                break
                            except btc.ApiError as error:
                                if error.status != 429:
                                    if error.status == 410:
                                        self.state = 'CLOSED'
                                        self.deadline = time.monotonic()
                                    raise
                                try:
                                    delay = float(error.retry_after)
                                except (TypeError, ValueError):
                                    delay = 15
                                if not 0 <= delay <= 300:
                                    delay = 15
                                if time.monotonic()+max(.25, delay) >= self.deadline:
                                    break
                                await asyncio.sleep(max(.25, delay))
                    except Exception as error:
                        self._log('pending', submission_id=packet['submission_id'], error_type=type(error).__name__)
                    finally:
                        self.queue.task_done()
            finally:
                poll.cancel()
                await asyncio.gather(poll, return_exceptions=True)

    def _thread(self):
        try:
            asyncio.run(self._run())
        except Exception as error:
            self.error = error
            self.ready.set()

    def __enter__(self):
        self.thread = threading.Thread(target=self._thread, daemon=True)
        self.thread.start()
        if not self.ready.wait(timeout=15):
            self.stop.set()
            raise TimeoutError('Status initialization timed out')
        if self.error:
            raise self.error
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=max(1, min(30, self.deadline-time.monotonic()+1)))
        if self.thread.is_alive():
            self._log('shutdown', reason='pending_outbox_requires_retry')
