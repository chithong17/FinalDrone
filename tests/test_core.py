import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import Detection, TelemetrySample
from src.evaluation import evaluate
from src.telemetry import Locator, Timeline, angular_distance, rules
from src.tracking import Tracker


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(Path('configs/offline.json').read_text())['location']
        self.cfg.update(heading_verified=True, scan_pose_verified=True)

    def test_floor_boundaries_and_gaps(self):
        for altitude, expected in [(-1,1), (6.99,1), (7,None), (7.39,None), (7.4,2), (9.3,2),
                (9.31,None), (10,3), (12.5,3), (12.6,None), (13,4), (15,4), (15.1,None), (15.5,5),
                (100,5), (None,None), (float('nan'),None), (float('inf'),None)]:
            with self.subTest(altitude=altitude):
                self.assertEqual(rules.floor_from_altitude(altitude), expected)

    def test_direction_wrap_and_boundaries(self):
        self.assertEqual([rules.direction_from_heading(x) for x in [-22.3, 67.7, 157.7, -112.3]],
                         ['NORTH', 'EAST', 'SOUTH', 'WEST'])
        for boundary in [-47, 7.1, 133, -173]:
            for delta in [-9.99, 0, 9.99]:
                self.assertIsNone(rules.direction_from_heading(boundary+delta))
        self.assertEqual(rules.direction_from_heading(180), rules.direction_from_heading(-180))
        self.assertAlmostEqual(angular_distance(179, -179), 2)

    def test_timeline_never_uses_future_or_duplicate_poll(self):
        timeline = Timeline([TelemetrySample(2, alt_rel=8), TelemetrySample(4, alt_rel=11)])
        self.assertIsNone(timeline.at(1.99))
        self.assertEqual(timeline.at(3).alt_rel, 8)
        timeline.add(TelemetrySample(4, alt_rel=99))
        self.assertEqual(len(timeline.points), 2)
        self.assertEqual(timeline.at(4).alt_rel, 11)

    def test_stable_scan_and_reject_off_center(self):
        timeline = Timeline([TelemetrySample(t, alt_rel=8, aircraft_yaw=-22.3) for t in [0, 2, 4]])
        result = Locator(self.cfg).locate(4.2, [45,20,55,60], (100,100), timeline)
        self.assertTrue(result.valid, result.reject_reasons)
        self.assertEqual((result.floor, result.direction), (2, 'NORTH'))
        result = Locator(self.cfg).locate(4.2, [0,20,10,60], (100,100), timeline)
        self.assertIn('target_off_center', result.reject_reasons)

    def test_unverified_stale_and_unstable(self):
        timeline = Timeline([TelemetrySample(0, alt_rel=8, aircraft_yaw=-22.3),
                             TelemetrySample(2, alt_rel=8.1, aircraft_yaw=0)])
        self.cfg['heading_verified'] = False
        result = Locator(self.cfg).locate(2.1, [45,20,55,60], (100,100), timeline)
        self.assertIn('heading_unverified', result.reject_reasons)
        self.assertIn('yaw_unstable', result.reject_reasons)
        result = Locator(self.cfg).locate(8, [45,20,55,60], (100,100), timeline)
        self.assertIn('telemetry_stale', result.reject_reasons)

    def test_original_recording_uses_manifest_clock_and_elevation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'manifest.json').write_text(json.dumps(dict(aircraft_sn='A', video_parts=[{'clock': {'t0':100}}])))
            records = [dict(topic='other', t=101, msg={'data':{'elevation':99}}),
                       dict(topic='thing/product/A/osd', t=102, msg={'data': {'elevation':8, 'height':99, 'attitude_head':67.7}})]
            (path/'telemetry.jsonl').write_text('\n'.join(map(json.dumps, records)))
            timeline = Timeline.load(path)
            self.assertEqual(timeline.t0,100)
            self.assertIsNone(timeline.at(1))
            self.assertEqual(timeline.at(2).alt_rel,8)


class TrackingTests(unittest.TestCase):
    def test_one_to_one_matching_and_track_expiry(self):
        tracker = Tracker(dict(iou_threshold=.3, max_gap_s=2))
        detections = [Detection([0,0,20,20], 'chair','chair',.9), Detection([30,0,50,20], 'chair','chair',.9)]
        first = tracker.update(detections,0)
        self.assertNotEqual(first[0].id, first[1].id)
        second = tracker.update(list(reversed(detections)),1)
        self.assertEqual([x.id for x in second], [first[1].id, first[0].id])
        third = tracker.update(detections,4)
        self.assertNotEqual(third[0].id, first[0].id)

    def test_ocr_consensus_does_not_lock_first_read(self):
        track = Tracker(dict(iou_threshold=.3,max_gap_s=2)).update([Detection([0,0,20,20],'chair','chair',.9)],0)[0]
        track.votes = [62]
        self.assertIsNone(track.consensus(2,.75))
        track.votes += [99,99,99]
        self.assertEqual(track.consensus(2,.75),99)


class EvaluationTests(unittest.TestCase):
    def test_pending_is_not_empty_ground_truth_and_decoy_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            obj = dict(bbox=[0,0,20,20], object_type='backpack',number=17,floor=2,direction='EAST')
            manifest = {'samples': [dict(sample_id='a',split='dev',annotation_status='reviewed',objects=[obj]),
                dict(sample_id='pending',split='dev',annotation_status='pending',objects=[]),
                dict(sample_id='decoy',split='dev',annotation_status='reviewed',objects=[dict(obj,decoy=True)])]}
            (root/'manifest.json').write_text(json.dumps(manifest))
            (root/'predictions.json').write_text(json.dumps({'a':[obj], 'pending':[obj], 'decoy':[obj]}))
            result = evaluate(root/'manifest.json',root/'predictions.json')
            self.assertEqual(result['counts']['skipped_pending_samples'],1)
            self.assertEqual(result['counts']['decoy_predictions'],1)
            self.assertEqual(result['counts']['complete_correct'],1)
            self.assertEqual(result['bbox_precision'],.5)


if __name__ == '__main__':
    unittest.main()
