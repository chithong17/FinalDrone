"""PTS-based replay and a bounded latest-frame RTSP source."""
import queue
import threading
import time
import uuid
from pathlib import Path

from .contracts import Frame


def make_frame(image, pts, epoch=None, jpeg=None):
    import cv2
    if jpeg is None:
        ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise ValueError('JPEG encoding failed')
        jpeg = encoded.tobytes()
    return Frame(uuid.uuid4().hex, image, jpeg, pts,
                 round(epoch*1000) if epoch is not None else int(time.time()*1000), time.monotonic())


def replay(path, start_s=0, step_s=0, limit=None, t0=None):
    import cv2
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}:
        from PIL import Image
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('Cannot decode image')
        with Image.open(path) as original:
            preserve_jpeg = original.format == 'JPEG' and original.getexif().get(274, 1) == 1
        # EXIF rotation is normalized in pixels so bbox and JPEG dimensions agree.
        yield make_frame(image, start_s, None if t0 is None else t0+start_s,
                         path.read_bytes() if preserve_jpeg else None)
        return
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError('Cannot open video')
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise ValueError('Video FPS missing')
        cap.set(cv2.CAP_PROP_POS_MSEC, start_s*1000)
        emitted, next_time, previous = 0, start_s, -1.0
        while limit is None or emitted < limit:
            ok, image = cap.read()
            if not ok:
                break
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if pts < previous:
                raise ValueError('Non-monotonic video timestamps')
            previous = pts
            if pts+1e-6 < next_time:
                continue
            yield make_frame(image, pts, None if t0 is None else t0+pts)
            emitted += 1
            next_time = pts+step_s
    finally:
        cap.release()


class LatestSource:
    def __init__(self, frames):
        self.frames = frames
        self.queue = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.done = threading.Event()
        self.error = None
        self.dropped = 0

    def __enter__(self):
        self.thread = threading.Thread(target=self._produce, daemon=True)
        self.thread.start()
        return self

    def _produce(self):
        try:
            for frame in self.frames:
                if self.stop.is_set():
                    break
                try:
                    self.queue.get_nowait()
                    self.dropped += 1
                except queue.Empty:
                    pass
                self.queue.put_nowait(frame)
        except Exception as error:
            self.error = error
        finally:
            self.done.set()

    def __iter__(self):
        while not self.done.is_set() or not self.queue.empty():
            try:
                yield self.queue.get(timeout=.2)
            except queue.Empty:
                continue
        if self.error:
            raise self.error

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=7)
        if self.thread.is_alive():
            raise RuntimeError('Source did not stop')


def paced(frames, stop):
    anchor, first = None, None
    for frame in frames:
        if anchor is None:
            anchor, first = time.monotonic(), frame.video_time_s
        if stop.wait(max(0, anchor+frame.video_time_s-first-time.monotonic())):
            break
        # Capture time for offline replay remains evidence time; monotonic is replay availability.
        frame.captured_monotonic = time.monotonic()
        yield frame


def rtsp_frames(url):
    import cv2
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                          [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
    try:
        if not cap.isOpened():
            raise ValueError('Cannot open RTSP; check source privately')
        while True:
            ok, image = cap.read()
            if not ok:
                raise RuntimeError('RTSP disconnected or read timeout')
            epoch = time.time()
            yield make_frame(image, epoch, epoch)
    finally:
        cap.release()
