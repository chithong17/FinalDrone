import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from src.contracts import Detection, NumberRead, TelemetrySample
from src.delivery import Delivery, btc, normalized_live_sample
from src.pipeline import Pipeline
from src.sources import make_frame, replay
from src.telemetry import Timeline
from src.vision import label_orientations


class PipelineTests(unittest.TestCase):
    def test_number_without_a4_or_unoriented_69_is_not_a_target(self):
        class Detector:
            def detect(self,image):
                return [Detection([40,10,60,80],'backpack','backpack',.99)]
        class OCR:
            def __init__(self,read):
                self.result=read
            def read(self,image,bbox):
                return self.result
        cfg=json.loads(Path('configs/offline.json').read_text())
        cfg['location'].update(heading_verified=True,scan_pose_verified=True)
        cfg['tracking']['min_votes']=1
        timeline=Timeline(TelemetrySample(t,alt_rel=8,aircraft_yaw=67.7) for t in [0,2,4])
        for read in [NumberRead('17',17,.99,[42,20,58,40]),
                     NumberRead('69',69,.99,[42,20,58,40],paper_bbox=[40,15,60,50])]:
            with tempfile.TemporaryDirectory() as tmp:
                pipeline=Pipeline(cfg,Detector(),OCR(read),timeline,tmp)
                pipeline.process(make_frame(np.full((100,100,3),128,np.uint8),4))
                self.assertEqual(pipeline.close()['candidates'],0)
                record=json.loads((Path(tmp)/'observations.jsonl').read_text())
                self.assertFalse(record['target_recognized'])

    def test_underline_fixes_orientation_without_flipping_99(self):
        image = np.full((200,320,3),255,dtype=np.uint8)
        cv2.putText(image,'99',(35,130),cv2.FONT_HERSHEY_SIMPLEX,3,(0,0,0),6)
        cv2.line(image,(30,160),(180,160),(0,0,0),5)
        self.assertEqual([r for _,r in label_orientations(image,[0,180])],[0])
        rotated = cv2.rotate(image,cv2.ROTATE_180)
        self.assertEqual([r for _,r in label_orientations(rotated,[0,180])],[180])

    def test_no_underline_does_not_invent_orientation(self):
        blank = np.full((100,200,3),255,dtype=np.uint8)
        self.assertEqual([r for _,r in label_orientations(blank,[0,180])],[0,180])

    def test_complete_observation_needs_consensus_and_preserves_evidence(self):
        class Detector:
            def detect(self, image):
                return [Detection([40,10,60,80], 'backpack','backpack',.99)]
        class OCR:
            def read(self, image, bbox):
                return NumberRead('17',17,.99,[42,20,58,40],paper_bbox=[40,15,60,50])
        cfg = json.loads(Path('configs/offline.json').read_text())
        cfg['location'].update(heading_verified=True,scan_pose_verified=True)
        timeline = Timeline(TelemetrySample(t,alt_rel=8,aircraft_yaw=67.7) for t in [0,2,4])
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = Pipeline(cfg,Detector(),OCR(),timeline,tmp)
            image = np.full((100,100,3),128,dtype=np.uint8)
            one, two = make_frame(image,2), make_frame(image,4)
            pipeline.process(one)
            self.assertEqual(pipeline.candidates,0)
            pipeline.process(two)
            report = pipeline.close()
            self.assertEqual(report['candidates'],1)
            record = json.loads((Path(tmp)/'candidates.jsonl').read_text().strip())
            self.assertEqual(record['ocr']['number'],17)
            self.assertEqual(record['location']['floor'],2)
            self.assertEqual(record['location']['direction'],'EAST')
            self.assertEqual((Path(tmp)/record['evidence']).read_bytes(),two.jpeg)

    def test_exif_rotation_keeps_evidence_and_bbox_dimensions_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'rotated.jpg'
            image = Image.new('RGB',(40,20),'orange')
            exif = Image.Exif()
            exif[274] = 6
            image.save(path,exif=exif)
            frame = next(replay(path))
            with Image.open(io.BytesIO(frame.jpeg)) as evidence:
                self.assertEqual(evidence.size,(frame.image.shape[1],frame.image.shape[0]))
                self.assertEqual(evidence.size,(20,40))

    def test_live_sample_requires_millisecond_clock(self):
        with self.assertRaises(ValueError):
            normalized_live_sample({'t_server':time.time()})
        sample = normalized_live_sample({'t_server':int(time.time()*1000),'alt_rel':8,'yaw':67.7})
        self.assertEqual(sample.alt_rel,8)
        self.assertEqual(sample.aircraft_yaw,67.7)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_429_retry_keeps_packet_and_persists_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = deepcopy(json.loads(Path('configs/offline.json').read_text())['delivery'])
            cfg['status_telemetry_path'] = 'telemetry'
            sender = Delivery(cfg,'http://unused','session',tmp,Timeline())
            packet = {'submission_id':'stable-id','image_b64':'same-evidence'}
            path = Path(tmp)/'outbox/stable-id.json'
            path.write_text(json.dumps(packet))
            sender.queue.put((path,packet))
            seen = []
            class FakeClient:
                def __init__(self,*args):
                    pass
                async def __aenter__(self):
                    return self
                async def __aexit__(self,*args):
                    pass
                async def status(self,session):
                    return {'state':'RUNNING','time_left_s':5,'telemetry':None}
                async def submit(self,payload):
                    seen.append(dict(payload))
                    if len(seen)==1:
                        raise btc.ApiError(429,{},retry_after='0')
                    sender.stop.set()
                    return dict(submission_id=payload['submission_id'],received_at_ms=1,status='pending_review')
            with patch.object(btc,'IndoorClient',FakeClient):
                await sender._run()
            self.assertEqual(seen,[packet,packet])
            self.assertTrue(path.with_suffix('.ack.json').is_file())
            self.assertEqual(json.loads(path.read_text()),packet)


if __name__ == '__main__':
    unittest.main()
