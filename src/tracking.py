"""Greedy one-to-one IoU tracking and per-track OCR consensus."""
from collections import Counter
from dataclasses import dataclass, field


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union if union else 0.0


@dataclass
class Track:
    id: int
    raw_class: str
    bbox: list[int]
    last_seen: float
    last_ocr: float = -1e10
    votes: list[int] = field(default_factory=list)
    best: dict | None = None
    emitted: bool = False

    def consensus(self, minimum, fraction):
        if not self.votes:
            return None
        number, count = Counter(self.votes).most_common(1)[0]
        return number if count >= minimum and count/len(self.votes) >= fraction else None


class Tracker:
    def __init__(self, config):
        self.config = config
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, time_s):
        self.tracks = {i: t for i, t in self.tracks.items() if time_s-t.last_seen <= self.config['max_gap_s']}
        pairs = sorted(((iou(t.bbox, d.bbox), i, j) for i, t in self.tracks.items()
                        for j, d in enumerate(detections) if t.raw_class == d.raw_class), reverse=True)
        matched, used, assigned = set(), set(), {}
        for score, i, j in pairs:
            if score < self.config['iou_threshold'] or i in matched or j in used:
                continue
            assigned[j] = self.tracks[i]
            matched.add(i)
            used.add(j)
        result = []
        for j, detection in enumerate(detections):
            track = assigned.get(j)
            if track is None:
                track = Track(self.next_id, detection.raw_class, detection.bbox, time_s)
                self.tracks[track.id] = track
                self.next_id += 1
            track.bbox, track.last_seen = detection.bbox, time_s
            result.append(track)
        return result
