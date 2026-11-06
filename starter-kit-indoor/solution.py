"""Submit a real detection, or retry the persisted packet. No fabricated detector."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from indoor_client import IndoorClient, make_packet, save_outbox


async def main(args):
    if args.retry:
        packet = json.loads(Path(args.retry).read_text(encoding='utf-8'))
    else:
        if not args.image or not args.detection:
            raise ValueError('Supply --image and --detection, or --retry')
        detection = json.loads(Path(args.detection).read_text(encoding='utf-8'))
        packet = make_packet(jpeg=Path(args.image).read_bytes(), **detection)
        save_outbox(args.outbox, packet)
    async with IndoorClient(args.server) as client:
        state = await client.status(packet['session_id'])
        print(json.dumps(state, ensure_ascii=False))
        # Retries may recover a previous ACK even if the round is closed.
        receipt = await client.submit(packet)
        print(json.dumps(receipt, ensure_ascii=False))
        if args.finish:
            print(await client.finish(packet['session_id']))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--image')
    parser.add_argument('--detection')
    parser.add_argument('--retry', help='Previously persisted outbox JSON')
    parser.add_argument('--outbox', default='outbox/packet.json')
    parser.add_argument('--finish', action='store_true', help='Irreversibly close the round after ACK')
    asyncio.run(main(parser.parse_args()))
