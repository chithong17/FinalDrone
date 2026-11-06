"""HTTP contract integration against a local fixture, not the BTC server.

Vision is deterministic here: this verifies transport, location and evidence.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from aiohttp import web
import numpy as np

from src.contracts import Detection, NumberRead
from src.delivery import Delivery, status_telemetry
from src.pipeline import Pipeline
from src.sources import make_frame
from src.telemetry import Timeline


class TelemetryDiscoveryTests(unittest.TestCase):
    def test_nested_exact_fields_and_missing(self):
        raw = dict(t_server=1793957645138, alt_rel=12.1, yaw=7.1)
        sample = status_telemetry({'data': {'flight': raw}}, 'auto')
        self.assertEqual(sample.aircraft_yaw, 7.1)
        self.assertEqual(sample.sample_time_ms, raw['t_server'])
        self.assertIsNone(status_telemetry({'state': 'RUNNING'}, 'auto'))
        self.assertIsNone(status_telemetry({'history': [raw]}, 'auto'))
        with self.assertRaises(ValueError):
            status_telemetry({'a': raw, 'b': raw}, 'auto')

    def test_bad_clock_or_nonfinite_not_accepted(self):
        for change in ({'t_server': time.time()}, {'yaw': float('nan')}, {'alt_rel': '12'}):
            raw = dict(t_server=1793957645138, alt_rel=12.1, yaw=7.1)
            raw.update(change)
            with self.assertRaises(ValueError):
                status_telemetry({'telemetry': raw}, 'auto')


class LiveHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_pipeline_submit_ack_real_http(self):
        stamp = round(time.time()*1000)
        seen = []
        async def status(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer fixture-token')
            return web.json_response(dict(state='RUNNING', time_left_s=10,
                flight_data=dict(t_server=stamp, alt_rel=8, yaw=67.7)))
        async def submit(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer fixture-token')
            packet = await request.json()
            seen.append(packet)
            return web.json_response(dict(submission_id=packet['submission_id'],
                received_at_ms=int(time.time()*1000), status='pending_review'))
        app = web.Application()
        app.router.add_get('/api/indoor/test-session/status', status)
        app.router.add_post('/api/indoor/submit_target', submit)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        class Detector:
            def detect(self, image):
                return [Detection([40,10,60,80], 'backpack','backpack',.99)]
        class OCR:
            def read(self, image, bbox):
                return NumberRead('17',17,.99,[42,20,58,40],paper_bbox=[40,15,60,50])
        try:
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, DRONE_TEAM_TOKEN='fixture-token'):
                cfg = json.loads(Path('configs/live.json').read_text())
                timeline = Timeline()
                sender = Delivery(cfg['delivery'], f'http://127.0.0.1:{port}', 'test-session', tmp, timeline)
                # Real IndoorClient, real HTTP status, and two distinct OSD samples.
                async with __import__('src.delivery', fromlist=['btc']).btc.IndoorClient(sender.server) as client:
                    await sender._status(client)
                    stamp += 1000
                    await sender._status(client)
                image = np.full((100,100,3),128,np.uint8)
                pipeline = Pipeline(cfg,Detector(),OCR(),timeline,tmp,'test-session',sender)
                one = make_frame(image, (stamp-1000)/1000, (stamp-1000)/1000)
                two = make_frame(image, stamp/1000, stamp/1000)
                pipeline.process(one, live=True)
                pipeline.process(two, live=True)
                self.assertEqual(pipeline.close()['candidates'], 1)
                sender.stop.set()  # Drain queued packet and persist ACK, then terminate.
                await sender._run()
                self.assertEqual(len(seen), 1)
                packet = seen[0]
                self.assertEqual((packet['floor'],packet['direction'],packet['number']), (2,'EAST',17))
                self.assertEqual(base64.b64decode(packet['image_b64']), two.jpeg)
                self.assertEqual(packet['bbox'], [40,10,60,80])
                self.assertEqual(packet['captured_at_ms'], two.captured_at_ms)
                acknowledgments = list((Path(tmp)/'outbox').glob('*.ack.json'))
                self.assertEqual(len(acknowledgments), 1)
                self.assertEqual(json.loads(acknowledgments[0].read_text())['status'], 'pending_review')
        finally:
            await runner.cleanup()


if __name__ == '__main__':
    unittest.main()
