"""HTTP client for Indoor M4E v1.1. Never requests flight authority."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import tempfile
from pathlib import Path

import aiohttp
from PIL import Image


class ApiError(Exception):
    def __init__(self, status, response, retry_after=None):
        super().__init__(f"HTTP {status}: {response}")
        self.status, self.response, self.retry_after = status, response, retry_after


class IndoorClient:
    def __init__(self, server, token=None):
        self.server = server.rstrip('/')
        self.token = token or os.environ.get('DRONE_TEAM_TOKEN', '')
        if not self.token:
            raise ValueError('Set DRONE_TEAM_TOKEN before connecting')
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers={'Authorization':f'Bearer {self.token}'},
                                            timeout=aiohttp.ClientTimeout(total=10))
        return self

    async def __aexit__(self, *_):
        await self.session.close()

    async def request(self, method, path, body=None):
        if self.session is None or self.session.closed:
            raise RuntimeError('Use async with IndoorClient(...)')
        # Serialize once: retries preserve submission_id AND exact evidence.
        data = json.dumps(body, allow_nan=False) if body is not None else None
        for attempt in range(3):
            try:
                async with self.session.request(method, self.server+path, data=data,
                                                headers={'Content-Type':'application/json'}) as response:
                    raw_text = await response.text()
                    try:
                        result = json.loads(raw_text)
                        if not isinstance(result, dict):
                            raise ValueError('Expected JSON object ACK')
                    except ValueError:
                        # Server (or a proxy/error page) returned non-JSON: never treat this as a
                        # successful ACK, surface the raw body through ApiError instead of crashing.
                        raise ApiError(response.status, raw_text,
                                       retry_after=response.headers.get('Retry-After'))
                    if response.status >= 400:
                        raise ApiError(response.status, result,
                                       retry_after=response.headers.get('Retry-After'))
                    return result
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(0.25*(2**attempt))

    async def status(self, session_id):
        return await self.request('GET', f'/api/indoor/{session_id}/status')

    async def submit(self, packet):
        result = await self.request('POST', '/api/indoor/submit_target', packet)
        if (result.get('submission_id') != packet['submission_id'] or
                result.get('status') != 'pending_review' or type(result.get('received_at_ms')) is not int):
            raise ApiError(200, 'Missing or mismatched submission ACK')
        return result

    async def finish(self, session_id):
        return await self.request('POST', f'/api/indoor/{session_id}/finish')


def make_packet(*, jpeg: bytes, session_id: str, submission_id: str, target_id: str,
                frame_id: str, captured_at_ms: int, object_type: str, number: int,
                floor: int, direction: str, bbox: list[int]):
    with Image.open(io.BytesIO(jpeg)) as image:
        if image.format != 'JPEG':
            raise ValueError('Evidence must be original JPEG')
        width, height = image.size
        image.load()
    if not (isinstance(bbox, list) and len(bbox) == 4 and all(type(x) is int for x in bbox)
            and 0 <= bbox[0] < bbox[2] <= width and 0 <= bbox[1] < bbox[3] <= height):
        raise ValueError('Map bbox back to original frame coordinates')
    return dict(session_id=session_id, submission_id=submission_id, target_id=target_id,
                frame_id=frame_id, captured_at_ms=captured_at_ms, image_width=width, image_height=height,
                object_type=object_type, number=number, floor=floor, direction=direction,
                bbox=bbox, image_b64=base64.b64encode(jpeg).decode('ascii'))


def save_outbox(path, packet):
    """Persist BEFORE first request; load same packet to retry after process failure.

    Writes to a temp file then renames (atomic on the same filesystem) so a crash or disk-full
    mid-write never leaves a partial/corrupt outbox file that a later --retry could misread.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Never silently overwrite an ID with different evidence.
    if dest.exists():
        if json.loads(dest.read_text(encoding='utf-8')) != packet:
            raise ValueError('Outbox packet already exists with different content')
        return
    fd, name = tempfile.mkstemp(prefix=dest.name+'.', suffix='.tmp', dir=dest.parent)
    temp = Path(name)
    try:
        os.close(fd)
        temp.write_text(json.dumps(packet, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        with temp.open('rb+') as stream:
            os.fsync(stream.fileno())
        # Publish complete bytes atomically, without replacing another writer's packet.
        try:
            os.link(temp, dest)
        except FileExistsError:
            if json.loads(dest.read_text(encoding='utf-8')) != packet:
                raise ValueError('Outbox packet already exists with different content')
    finally:
        temp.unlink(missing_ok=True)
