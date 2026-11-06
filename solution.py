"""Submission entrypoint. Run from the extracted submission directory."""
import sys
from datetime import datetime
from pathlib import Path

from src.cli import main


if __name__ == '__main__':
    arguments = sys.argv[1:]
    if not any(a == '--mode' or a.startswith('--mode=') for a in arguments):
        live = any(a == '--server' or a.startswith('--server=') for a in arguments)
        arguments += ['--mode', 'live' if live else 'offline']
    live_mode = ('live' in arguments and '--mode' in arguments) or '--mode=live' in arguments
    if live_mode and not any(a == '--config' or a.startswith('--config=') for a in arguments):
        arguments += ['--config', str(Path(__file__).resolve().parent / 'configs/live.json')]
    if not any(a == '--output' or a.startswith('--output=') for a in arguments):
        arguments += ['--output', 'output/run-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')]
    sys.argv = [sys.argv[0], 'run', *arguments]
    main()
