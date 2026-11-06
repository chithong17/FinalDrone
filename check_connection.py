"""Read-only status/schema check; does not submit targets or finish a session."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path


def schema(value):
    if isinstance(value, dict):
        return {key: schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [schema(value[0])] if value else []
    return type(value).__name__


async def check(args):
    path = Path(__file__).resolve().parent / 'starter-kit-indoor/indoor_client.py'
    spec = importlib.util.spec_from_file_location('btc_probe_client', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        async with module.IndoorClient(args.server) as client:
            status = await client.status(args.session)
    except module.ApiError as error:
        raise SystemExit(f'API HTTP {error.status}; check token, session and server logs.') from None
    except Exception as error:
        raise SystemExit(f'Connection failed ({type(error).__name__}); check server and DRONE_TEAM_TOKEN.') from None
    report = {'connected': True, 'status_schema': schema(status)}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('GET status OK. No target submitted. Schema saved to', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:20201')
    parser.add_argument('--session', required=True)
    parser.add_argument('--output', default='output/connection-schema.json')
    asyncio.run(check(parser.parse_args()))
