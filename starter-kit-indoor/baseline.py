"""CPU baseline: original frame -> YOLO -> HSV/OCR/venue ROI -> durable outbox.

No flight endpoints. Missing/ambiguous recognition is rejected, never defaulted.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import uuid

from PIL import Image
from indoor_client import ApiError, IndoorClient, make_packet, save_outbox


class Rejected(ValueError):
    """Observation lacks calibrated evidence; do not submit it."""


@dataclass
class Frame:
    image: object  # OpenCV BGR array at original source resolution
    jpeg: bytes
    frame_id: str
    captured_at_ms: int
    captured_monotonic: float


def frame_from_bgr(image, jpeg=None):
    import cv2
    if jpeg is None:
        ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise Rejected('JPEG encode failed')
        jpeg = data.tobytes()
    return Frame(image, jpeg, uuid.uuid4().hex, int(time.time()*1000), time.monotonic())


class FrameSource:
    """One image or bounded video/RTSP reader, capacity one, newest frame wins.

    Video files are paced using FPS so EOF does not discard the whole file before
    inference starts. RTSP reads use OpenCV/FFmpeg open/read timeouts.
    """
    def __init__(self, source):
        self.source = source
        self.queue = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.done = threading.Event()
        self.thread = None
        self.error = None
        self.cap = None

    def __enter__(self):
        self.thread = threading.Thread(target=self._produce, name='latest-frame', daemon=True)
        self.thread.start()
        return self

    def _offer(self, frame):
        try:
            self.queue.get_nowait()
        except queue.Empty:
            pass
        self.queue.put_nowait(frame)

    def _produce(self):
        import cv2
        try:
            path = Path(self.source)
            if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'} and path.is_file():
                image = cv2.imread(str(path))
                if image is None:
                    raise Rejected('Cannot decode image')
                raw = path.read_bytes() if path.suffix.lower() in {'.jpg', '.jpeg'} else None
                self._offer(frame_from_bgr(image, raw))
                return
            stream = self.source.lower().startswith(('rtsp://', 'http://', 'https://'))
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
            if not self.cap.isOpened():
                raise Rejected('Cannot open video/RTSP (check source privately)')
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not stream and (not math.isfinite(fps) or fps <= 0):
                raise Rejected('Video has no usable FPS')
            start, index = time.monotonic(), 0
            while not self.stop.is_set():
                ok, image = self.cap.read()
                if not ok:
                    if stream:
                        raise Rejected('RTSP disconnected/read timeout')
                    break
                if not stream and self.stop.wait(max(0, start+index/fps-time.monotonic())):
                    break
                index += 1
                self._offer(frame_from_bgr(image))
        except Exception as error:
            # Do not echo source URLs that may contain credentials.
            self.error = Rejected(f'Frame source failed ({type(error).__name__})')
        finally:
            if self.cap is not None:
                self.cap.release()
            self.done.set()

    def next(self, timeout=.5):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            if self.error:
                raise self.error
            if self.done.is_set():
                raise StopIteration
            return None

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=7)
        if self.thread.is_alive():
            raise RuntimeError('Frame reader did not stop within read timeout')


class SampleTelemetry:
    """Offline timeline from sample_telemetry.json; t=0 aligns with first decoded video frame."""

    def __init__(self, path):
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(raw, list) or not raw:
            raise ValueError('Telemetry file must be a non-empty JSON array')
        self.points = sorted(raw, key=lambda p: p['time_offset_s'])

    def at(self, t_s):
        pts = self.points
        if t_s < pts[0]['time_offset_s']:
            return None
        lo, hi = 0, len(pts) - 1
        if t_s >= pts[hi]['time_offset_s']:
            return pts[hi]
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if pts[mid]['time_offset_s'] <= t_s:
                lo = mid
            else:
                hi = mid - 1
        return pts[lo]


def sync_telemetry(telemetry, frame, video_anchor):
    if telemetry is None:
        return video_anchor, None
    if video_anchor is None:
        video_anchor = frame.captured_monotonic
    return video_anchor, telemetry.at(frame.captured_monotonic - video_anchor)


def print_telemetry_sync(frame, sample):
    if not sample:
        return
    print(json.dumps({'type': 'telemetry_sync', 'frame_id': frame.frame_id, **sample}, ensure_ascii=False))


def original_bbox(box, width, height):
    if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
        raise Rejected('Invalid detector bbox')
    x1, y1 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
    x2, y2 = min(width, math.ceil(box[2])), min(height, math.ceil(box[3]))
    if x2 <= x1 or y2 <= y1:
        raise Rejected('Empty detector bbox')
    return [x1, y1, x2, y2]


def remap_letterbox(box, original_size, input_size):
    """Adapter utility for custom backends returning padded model coordinates."""
    w, h = original_size
    mw, mh = input_size
    scale = min(mw/w, mh/h)
    px, py = (mw-w*scale)/2, (mh-h*scale)/2
    return original_bbox([(box[0]-px)/scale, (box[1]-py)/scale,
                          (box[2]-px)/scale, (box[3]-py)/scale], w, h)


class YoloDetector:
    def __init__(self, weights, *, class_map=None, imgsz=640, confidence=.35):
        from ultralytics import YOLO
        import torch
        torch.set_num_threads(2)
        if not Path(weights).is_file():
            raise ValueError('Supply a local YOLO weight file; no implicit model download')
        self.model = YOLO(weights)
        self.imgsz, self.confidence = imgsz, confidence
        self.class_map = class_map
        if class_map is None:
            # Name based, never confuse COCO orange fruit/fire hydrant with targets.
            names = set(self.model.names.values())
            if not {'backpack', 'chair'} <= names:
                raise ValueError('Default adapter requires COCO chair/backpack classes')
        elif not class_map or any(v not in {'chair', 'chair_orange', 'chair_white', 'chair_gray',
                                           'backpack', 'fire_extinguisher'} for v in class_map.values()):
            raise ValueError('Invalid explicit custom class map')

    def detect(self, image):
        result = self.model.predict(image, imgsz=self.imgsz, device='cpu',
                                    conf=self.confidence, verbose=False, max_det=30)[0]
        h, w = image.shape[:2]
        if tuple(result.orig_shape) != (h, w):
            raise Rejected('Detector original shape mismatch')
        found = []
        for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
            name = self.model.names[int(cls)]
            target = (self.class_map.get(str(int(cls))) or self.class_map.get(name)) if self.class_map is not None else {'backpack':'backpack', 'chair':'chair'}.get(name)
            if target:
                # Ultralytics Results.xyxy already undoes resize/letterbox to orig_shape.
                found.append((target, original_bbox(box, w, h)))
        return found


def relative_crop(image, roi):
    if (not isinstance(roi, list) or len(roi) != 4 or
            not all(type(v) in (float, int) and math.isfinite(v) for v in roi) or
            not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1)):
        raise Rejected('ROI must be normalized [x1,y1,x2,y2]')
    h, w = image.shape[:2]
    x1, y1, x2, y2 = original_bbox([roi[0]*w, roi[1]*h, roi[2]*w, roi[3]*h], w, h)
    return image[y1:y2, x1:x2]


class ChairColor:
    def __init__(self, config):
        self.config = config
        if set(config.get('ranges', {})) != {'chair_orange', 'chair_white', 'chair_gray'}:
            raise ValueError('Calibrate all three chair HSV ranges')

    def classify(self, crop):
        import cv2
        import numpy as np
        hsv = cv2.cvtColor(relative_crop(crop, self.config['sample_roi']), cv2.COLOR_BGR2HSV)
        scores = {}
        for name, bounds in self.config['ranges'].items():
            mask = cv2.inRange(hsv, np.array(bounds[0], dtype=np.uint8), np.array(bounds[1], dtype=np.uint8))
            scores[name] = float(np.count_nonzero(mask))/mask.size
        ranked = sorted(scores, key=scores.get, reverse=True)
        if scores[ranked[0]] < self.config['min_fraction'] or scores[ranked[0]]-scores[ranked[1]] < self.config['min_margin']:
            raise Rejected('Chair color ambiguous; recalibrate HSV/ROI')
        return ranked[0]


def parse_number(text, confidence, minimum):
    # Require an actual two-digit label. Do not strip letters or invent a leading 0.
    text = text.strip()
    if not math.isfinite(confidence) or confidence < minimum or not re.fullmatch(r'0[1-9]|[1-9][0-9]', text):
        raise Rejected('OCR must confidently read exactly 01–99')
    return int(text)


class TesseractDigits:
    """Local CPU subprocess with timeout, TSV confidence and strict digit grammar."""
    def __init__(self, executable, tessdata, config):
        self.executable = str(Path(executable).resolve())
        self.tessdata = str(Path(tessdata).resolve())
        if not Path(self.executable).is_file() or not (Path(self.tessdata)/'eng.traineddata').is_file():
            raise ValueError('Supply local Tesseract executable and eng tessdata directory')
        self.config = config

    def read(self, object_crop):
        import cv2
        crop = relative_crop(object_crop, self.config['label_roi'])
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        scale = max(1, 96/gray.shape[0])
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        if binary.mean() < 127:
            binary = cv2.bitwise_not(binary)
        binary = cv2.copyMakeBorder(binary, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
        ok, encoded = cv2.imencode('.png', binary)
        if not ok:
            raise Rejected('OCR crop encode failed')
        result = subprocess.run([self.executable, 'stdin', 'stdout', '--tessdata-dir', self.tessdata,
            '--psm', '7', '-l', 'eng', '-c', 'tessedit_char_whitelist=0123456789',
            '-c', 'tessedit_create_tsv=1'],
            input=encoded.tobytes(), capture_output=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise Rejected('Tesseract failed')
        words = []
        for line in result.stdout.decode('utf-8').splitlines()[1:]:
            cols = line.split('\t')
            if len(cols) == 12 and cols[0] == '5' and cols[11].strip():
                words.append((cols[11], float(cols[10])))
        if len(words) != 1:
            raise Rejected('OCR missing or ambiguous number label')
        return parse_number(words[0][0], words[0][1], self.config['min_confidence'])


class VenueCalibration:
    def __init__(self, config, view, allow_example=False):
        if config.get('example_only') is not False and not allow_example:
            raise ValueError('Example calibration is synthetic; calibrate venue and set example_only=false')
        if view not in config['views']:
            raise ValueError('Unknown calibrated camera view')
        self.view = config['views'][view]

    def locate(self, bbox, size):
        if list(size) != self.view['image_size']:
            raise Rejected('Frame resolution differs from calibrated view')
        w, h = size
        x, y = (bbox[0]+bbox[2])/2/w, (bbox[1]+bbox[3])/2/h
        matches = [r for r in self.view['regions'] if r['roi'][0] <= x < r['roi'][2] and r['roi'][1] <= y < r['roi'][3]]
        if len(matches) != 1:
            raise Rejected('Target outside or ambiguously inside calibrated building sectors')
        region = matches[0]
        if type(region['floor']) is not int or not 1 <= region['floor'] <= 5 or region['direction'] not in {'NORTH','SOUTH','EAST','WEST'}:
            raise Rejected('Invalid building sector calibration')
        return region['floor'], region['direction']


class Pipeline:
    def __init__(self, detector, color, ocr, calibration, max_age_s=2):
        self.detector, self.color, self.ocr, self.calibration = detector, color, ocr, calibration
        self.max_age_s = max_age_s

    def packets(self, frame, session_id):
        if time.monotonic()-frame.captured_monotonic > self.max_age_s:
            raise Rejected('Stale frame; reacquire latest frame')
        with Image.open(io.BytesIO(frame.jpeg)) as original:
            w, h = original.size
        if (w, h) != (frame.image.shape[1], frame.image.shape[0]):
            raise Rejected('JPEG/source shape mismatch')
        for kind, bbox in self.detector.detect(frame.image):
            try:
                bbox = original_bbox(bbox, w, h)
                x1,y1,x2,y2 = bbox
                crop = frame.image[y1:y2,x1:x2]
                if kind == 'chair':
                    kind = self.color.classify(crop)
                number = self.ocr.read(crop)
                floor, direction = self.calibration.locate(bbox, (w,h))
                if time.monotonic()-frame.captured_monotonic > self.max_age_s:
                    raise Rejected('Frame became stale during inference/OCR')
                yield make_packet(jpeg=frame.jpeg, session_id=session_id, submission_id=uuid.uuid4().hex,
                    target_id=f'observed-{number:02d}', frame_id=frame.frame_id,
                    captured_at_ms=frame.captured_at_ms, object_type=kind, number=number,
                    floor=floor, direction=direction, bbox=bbox)
            except Rejected as error:
                print(f'Observation rejected: {error}')


async def send_saved(client, path, packet, deadline):
    save_outbox(path, packet)
    while True:
        try:
            return await client.submit(packet)
        except ApiError as error:
            if error.status != 429:
                raise
            try:
                delay = float(error.retry_after)
            except (TypeError, ValueError):
                delay = 15
            if not math.isfinite(delay) or delay < 0:
                delay = 15
            delay = max(.25, min(delay, 300))
            if time.monotonic()+delay >= deadline:
                raise Rejected('Round ends before quota retry; outbox preserved')
            await asyncio.sleep(delay)


async def run(args):
    import numpy as np
    telemetry = SampleTelemetry(args.telemetry) if args.telemetry else None
    video_anchor = None
    config = json.loads(Path(args.calibration).read_text(encoding='utf-8'))
    calibration = VenueCalibration(config, args.view, args.allow_example)
    mapping = json.loads(Path(args.class_map).read_text()) if args.class_map else None
    detector = YoloDetector(args.weights, class_map=mapping, imgsz=args.imgsz)
    # Allocate CPU inference buffers before capturing evidence; never submit warmup frames.
    detector.detect(np.zeros((args.imgsz,args.imgsz,3),dtype=np.uint8))
    ocr = TesseractDigits(args.tesseract, args.tessdata, config['ocr'])
    pipeline = Pipeline(detector, ChairColor(config['chair_color']), ocr, calibration, args.max_age)
    if mapping is None:
        print('COCO baseline: chair + backpack only. Fire extinguisher unsupported; supply custom weights/class-map.')
    async with IndoorClient(args.server) as client:
        state = await client.status(args.session)
        if state['state'] != 'RUNNING':
            raise Rejected('Round is not RUNNING; use solution.py --retry for saved ACK recovery')
        deadline = time.monotonic()+min(300, state['time_left_s'])
        sent = set()
        frames = 0
        with FrameSource(args.source) as source:
            while time.monotonic() < deadline and frames < args.max_frames:
                try:
                    frame = source.next()
                except StopIteration:
                    break
                if frame is None:
                    continue
                frames += 1
                video_anchor, tel = sync_telemetry(telemetry, frame, video_anchor)
                print_telemetry_sync(frame, tel)
                try:
                    for packet in pipeline.packets(frame, args.session):
                        # Conservative traffic suppression only, never scoring/physical identity.
                        key = (packet['object_type'],packet['number'],packet['floor'],packet['direction'])
                        if key in sent:
                            continue
                        path = Path(args.outbox)/f"{packet['submission_id']}.json"
                        ack = await send_saved(client, path, packet, deadline)
                        print(json.dumps(ack))
                        sent.add(key)
                except Rejected as error:
                    print(f'Frame rejected: {error}')
        print(f'Processed {frames} frame(s); round remains under server clock. No automatic finish.')


def run_offline_pipeline(args):
    import numpy as np
    telemetry = SampleTelemetry(args.telemetry) if args.telemetry else None
    video_anchor = None
    if not args.calibration:
        raise ValueError('Missing --calibration (e.g. venue.json or calibration.example.json)')
    config = json.loads(Path(args.calibration).read_text(encoding='utf-8'))
    view = args.view or next(iter(config.get('views', {})), 'default')
    calibration = VenueCalibration(config, view, args.allow_example)
    mapping = json.loads(Path(args.class_map).read_text()) if args.class_map else None
    detector = YoloDetector(args.weights, class_map=mapping, imgsz=args.imgsz)
    detector.detect(np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8))
    ocr = TesseractDigits(args.tesseract, args.tessdata, config['ocr'])
    pipeline = Pipeline(detector, ChairColor(config['chair_color']), ocr, calibration, args.max_age)
    
    outbox = Path(args.outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    session = args.session or "offline_practice"
    sent = set()
    frames = 0
    with FrameSource(args.source) as source:
        while frames < args.max_frames:
            try:
                frame = source.next()
            except StopIteration:
                break
            if frame is None:
                continue
            frames += 1
            video_anchor, tel = sync_telemetry(telemetry, frame, video_anchor)
            print_telemetry_sync(frame, tel)
            try:
                for packet in pipeline.packets(frame, session):
                    key = (packet['object_type'], packet['number'], packet['floor'], packet['direction'])
                    if key in sent:
                        continue
                    path = outbox / f"{packet['submission_id']}.json"
                    path.write_text(json.dumps(packet, indent=2), encoding='utf-8')
                    print(f"[OFFLINE DETECTED] Saved to outbox: {path.name} -> {packet['object_type']}, number={packet['number']}, floor={packet['floor']}, dir={packet['direction']}")
                    sent.add(key)
            except Rejected as error:
                pass
    print(f'Offline processing finished: {frames} frame(s), {len(sent)} target(s) detected.')


def run_offline_preview(args):
    telemetry = SampleTelemetry(args.telemetry)
    video_anchor = None
    frames = 0
    with FrameSource(args.source) as source:
        while frames < args.max_frames:
            try:
                frame = source.next()
            except StopIteration:
                break
            if frame is None:
                continue
            frames += 1
            video_anchor, tel = sync_telemetry(telemetry, frame, video_anchor)
            print_telemetry_sync(frame, tel)
    print(f'Offline preview: {frames} frame(s) with telemetry (no server).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--telemetry', help='Offline telemetry JSON synced to video time=0 at first frame')
    for name in ('server', 'session', 'weights', 'calibration', 'view', 'tesseract', 'tessdata'):
        parser.add_argument('--'+name)
    parser.add_argument('--class-map', help='Explicit custom model class name/id to target type JSON')
    parser.add_argument('--allow-example', action='store_true', help='Synthetic fixtures only')
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--max-age', type=float, default=5)
    parser.add_argument('--max-frames', type=int, default=100000)
    parser.add_argument('--outbox', default='outbox')
    args = parser.parse_args()
    if args.max_age <= 0 or not math.isfinite(args.max_age) or args.max_frames < 1:
        parser.error('max-age must be finite positive; max-frames >=1')
    # Smart defaults for local bundle assets if omitted
    if not args.tesseract and Path('tools/tesseract/tesseract.exe').is_file():
        args.tesseract = 'tools/tesseract/tesseract.exe'
    if not args.tessdata and Path('models/tessdata').is_dir():
        args.tessdata = 'models/tessdata'
    if not args.weights and Path('models/yolov8n.pt').is_file():
        args.weights = 'models/yolov8n.pt'
    if not args.calibration:
        if Path('venue.json').is_file():
            args.calibration = 'venue.json'
        elif Path('calibration.example.json').is_file():
            args.calibration = 'calibration.example.json'
            args.allow_example = True

    # Pure offline simulation mode (no server, or explicit outbox saving)
    if not args.server:
        run_offline_pipeline(args)
        return
    missing = [n for n in ('server', 'session', 'weights', 'calibration', 'view', 'tesseract', 'tessdata')
               if not getattr(args, n)]
    if missing:
        parser.error('missing required flags: ' + ', '.join('--'+m for m in missing))
    asyncio.run(run(args))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
