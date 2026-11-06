"""Timestamp-based telemetry, shared by replay and live adapters."""
import bisect
import importlib.util
import json
import math
import threading
from pathlib import Path

from .contracts import LocationResult, TelemetrySample

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('scan_rules', ROOT / 'starter-kit-indoor/telemetry_location.py')
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def angular_distance(a, b):
    return abs((a - b + 180) % 360 - 180)


def from_osd(row, t0, payload):
    data = row.get('msg', {}).get('data', {})
    camera = data.get(payload) or {}
    return TelemetrySample(
        video_time_s=row['t'] - t0, sample_time_ms=round(row['t'] * 1000),
        alt_rel=data.get('elevation'), aircraft_yaw=data.get('attitude_head'),
        gimbal_yaw=camera.get('gimbal_yaw'), gimbal_pitch=camera.get('gimbal_pitch'),
        zoom_factor=camera.get('zoom_factor'))


class Timeline:
    def __init__(self, points=()):
        self.points = sorted(points, key=lambda p: p.video_time_s)
        self.times = [p.video_time_s for p in self.points]
        self.t0 = None
        self.lock = threading.RLock()

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.is_dir():
            manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8-sig'))
            t0 = manifest['video_parts'][0]['clock']['t0']
            topic = f"thing/product/{manifest['aircraft_sn']}/osd"
            points = []
            with (path / 'telemetry.jsonl').open(encoding='utf-8-sig') as stream:
                for line in stream:
                    if line.strip():
                        row = json.loads(line)
                        if row.get('topic') == topic:
                            points.append(from_osd(row, t0, manifest.get('payload_index') or '88-0-0'))
            result = cls(points)
            result.t0 = t0
            return result
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        return cls(TelemetrySample(video_time_s=p['time_offset_s'], alt_rel=p.get('alt_rel'),
                   aircraft_yaw=p.get('attitude_head', p.get('yaw')), gimbal_yaw=p.get('gimbal_yaw'),
                   gimbal_pitch=p.get('gimbal_pitch'), zoom_factor=p.get('zoom_factor')) for p in raw)

    def at(self, time_s):
        with self.lock:
            i = bisect.bisect_right(self.times, time_s) - 1
            return self.points[i] if i >= 0 else None

    def history(self, time_s, window):
        with self.lock:
            return self.points[bisect.bisect_left(self.times, time_s-window):bisect.bisect_right(self.times, time_s)]

    def add(self, sample):
        with self.lock:
            i = bisect.bisect_left(self.times, sample.video_time_s)
            if i < len(self.times) and self.times[i] == sample.video_time_s:
                return  # Re-polling cached OSD does not create another stability vote.
            self.times.insert(i, sample.video_time_s)
            self.points.insert(i, sample)
            if len(self.points) > 1000:
                self.points.pop(0)
                self.times.pop(0)


class Locator:
    def __init__(self, config):
        self.config = config
        self.rules_config = rules.load_config()

    def locate(self, frame_time, bbox, size, timeline):
        cfg = self.config
        time_s = frame_time + cfg['telemetry_offset_s']
        sample = timeline.at(time_s)
        out = LocationResult()
        if sample is None:
            out.reject_reasons.append('telemetry_missing')
            return out
        out.telemetry_age_s = time_s-sample.video_time_s
        if out.telemetry_age_s > cfg['max_telemetry_age_s']:
            out.reject_reasons.append('telemetry_stale')
        out.floor = rules.floor_from_altitude(sample.alt_rel, self.rules_config)
        heading = getattr(sample, cfg['heading_field'], None)
        out.direction = rules.direction_from_heading(heading, self.rules_config)
        if out.floor is None:
            out.reject_reasons.append('altitude_outside_bands')
        if out.direction is None:
            out.reject_reasons.append('heading_missing_or_boundary')
        if not cfg['heading_verified']:
            out.reject_reasons.append('heading_unverified')
        if not cfg['scan_pose_verified']:
            out.reject_reasons.append('scan_pose_unverified')
        center_x = (bbox[0]+bbox[2]) / (2*size[0])
        if abs(center_x-0.5) > cfg['center_fraction']/2:
            out.reject_reasons.append('target_off_center')
        history = timeline.history(time_s, cfg['stability_window_s'])
        if len(history) < cfg['min_stable_samples']:
            out.reject_reasons.append('insufficient_stability_samples')
        elif not finite(heading) or any(not finite(getattr(p, cfg['heading_field'], None)) or
                not finite(p.alt_rel) for p in history) or not finite(sample.alt_rel):
            out.reject_reasons.append('stability_data_missing')
        else:
            if any(angular_distance(getattr(p, cfg['heading_field']), heading) > cfg['max_yaw_spread_deg'] for p in history):
                out.reject_reasons.append('yaw_unstable')
            if max(p.alt_rel for p in history)-min(p.alt_rel for p in history) > cfg['max_alt_spread_m']:
                out.reject_reasons.append('altitude_unstable')
        pitch_range = cfg.get('gimbal_pitch_range')
        if pitch_range is not None and (not finite(sample.gimbal_pitch) or
                not pitch_range[0] <= sample.gimbal_pitch <= pitch_range[1]):
            out.reject_reasons.append('gimbal_pitch_outside_scan_pose')
        return out
