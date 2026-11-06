import json
import statistics
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .contracts import NumberRead
from .telemetry import Locator
from .tracking import Tracker
from .vision import classify_chair


class Pipeline:
    def __init__(self, config, detector, ocr, timeline, output, session_id=None, delivery=None):
        self.config, self.detector, self.ocr, self.timeline = config, detector, ocr, timeline
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / 'evidence').mkdir(exist_ok=True)
        (self.output / 'debug').mkdir(exist_ok=True)
        (self.output / 'crops').mkdir(exist_ok=True)
        self.tracker, self.locator = Tracker(config['tracking']), Locator(config['location'])
        self.session_id, self.delivery = session_id, delivery
        self.latencies, self.age_ms, self.rejections = [], [], Counter()
        self.frames, self.candidates, self.observations = 0, 0, 0
        self.peak_rss_mb = 0
        self.log = (self.output / 'observations.jsonl').open('w', encoding='utf-8')
        self.candidate_log = (self.output / 'candidates.jsonl').open('w', encoding='utf-8')

    def process(self, frame, debug=False, live=False):
        import cv2
        start = time.perf_counter()
        detections = self.detector.detect(frame.image)
        tracks = self.tracker.update(detections, frame.video_time_s)
        annotated = frame.image.copy() if debug else None
        for detection, track in zip(detections, tracks):
            x1, y1, x2, y2 = detection.bbox
            if detection.object_type == 'chair':
                detection.object_type = classify_chair(frame.image[y1:y2, x1:x2], self.config['color'])
            read = NumberRead(reject_reason='ocr_throttled')
            if frame.video_time_s-track.last_ocr >= self.config['tracking']['ocr_every_s']:
                read = (self.ocr.read(frame.image, detection.bbox,label_hint=detection.label_bbox)
                        if detection.label_bbox is not None else self.ocr.read(frame.image, detection.bbox))
                track.last_ocr = frame.video_time_s
                if read.number is not None:
                    track.votes.append(read.number)
                    track.votes = track.votes[-20:]
            location = self.locator.locate(frame.video_time_s, detection.bbox,
                                           (frame.image.shape[1], frame.image.shape[0]), self.timeline)
            reasons = list(location.reject_reasons)
            if detection.object_type is None:
                reasons.append('object_color_ambiguous')
            if read.number is None:
                reasons.append(read.reject_reason)
            if read.paper_bbox is None:
                reasons.append('a4_number_paper_required')
            if read.text and any(digit in '69' for digit in read.text) and not read.orientation_verified:
                reasons.append('underline_orientation_required')
            consensus = track.consensus(self.config['tracking']['min_votes'], self.config['tracking']['vote_fraction'])
            if consensus is None or consensus != read.number:
                reasons.append('number_not_confirmed')
            if live and time.monotonic()-frame.captured_monotonic > 3:
                reasons.append('frame_stale')
            record = dict(frame_id=frame.frame_id, video_time_s=frame.video_time_s,
                          captured_at_ms=frame.captured_at_ms, track_id=track.id,
                          detection=asdict(detection), ocr=asdict(read), location=asdict(location),
                          confirmed_number=consensus, reject_reasons=reasons)
            record['target_recognized'] = (read.number is not None and read.paper_bbox is not None and
                (not any(digit in '69' for digit in (read.text or '')) or read.orientation_verified))
            sample = self.timeline.at(frame.video_time_s+self.config['location']['telemetry_offset_s'])
            record['telemetry'] = asdict(sample) if sample else None
            self.log.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')
            self.observations += 1
            self.rejections.update(reasons)
            if read.label_bbox and debug:
                a, b, c, d = read.label_bbox
                cv2.imwrite(str(self.output / 'crops' / f'{frame.frame_id}-{track.id}.jpg'), frame.image[b:d, a:c])
            if not reasons:
                sharpness = cv2.Laplacian(cv2.cvtColor(frame.image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                quality = float(read.confidence) * detection.confidence * (1+min(float(sharpness), 1000)/1000)
                if track.best is None or quality > track.best['quality']:
                    track.best = {'quality': quality, 'observation': record}
                    evidence = self.output / 'evidence' / f'track-{track.id}-{frame.frame_id}.jpg'
                    evidence.write_bytes(frame.jpeg)
                    candidate = dict(record, evidence=str(evidence.relative_to(self.output)), quality=quality)
                    self.candidate_log.write(json.dumps(candidate, ensure_ascii=False, allow_nan=False)+'\n')
                    self.candidate_log.flush()
                    self.candidates += 1
                    if self.delivery is not None and not track.emitted:
                        # Queue acceptance is not an ACK. Delivery keeps durable retry state.
                        track.emitted = self.delivery.enqueue(frame, detection, read, location, track.id)
            if debug and record['target_recognized']:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 255), 2)
                text = f'{detection.object_type}  #{read.text}'
                if location.floor is not None and location.direction is not None:
                    text += f'  F{location.floor} {location.direction}'
                font_scale=max(.6,min(1.5,frame.image.shape[1]/1400))
                (tw,th),baseline=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,font_scale,2)
                tx=max(0,min(x1,annotated.shape[1]-tw-12))
                ty=max(th+10,y1-10)
                cv2.rectangle(annotated,(tx,ty-th-8),(tx+tw+10,ty+baseline+3),(20,24,32),-1)
                cv2.putText(annotated,text,(tx+5,ty),cv2.FONT_HERSHEY_SIMPLEX,font_scale,(0,220,255),2)
        if debug:
            cv2.imwrite(str(self.output / 'debug' / f'{frame.frame_id}.jpg'), annotated)
        self.log.flush()
        self.frames += 1
        if self.frames == 1 or self.frames % 30 == 0:
            import psutil
            self.peak_rss_mb = max(self.peak_rss_mb, psutil.Process().memory_info().rss/1024**2)
        self.latencies.append((time.perf_counter()-start)*1000)
        self.age_ms.append((time.monotonic()-frame.captured_monotonic)*1000)

    def close(self):
        self.log.close()
        self.candidate_log.close()
        ordered = sorted(self.latencies)
        summary = dict(frames=self.frames, observations=self.observations, candidates=self.candidates,
                       sampled_peak_rss_mb=self.peak_rss_mb,
                       rejection_counts=dict(self.rejections),
                       processing_p50_ms=statistics.median(ordered) if ordered else None,
                       processing_p95_ms=ordered[min(len(ordered)-1, int(len(ordered)*.95))] if ordered else None,
                       max_frame_age_ms=max(self.age_ms, default=0))
        (self.output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        return summary
