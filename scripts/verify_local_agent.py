"""Run actual CLI/SDK/RPC acceptance against a running self-hosted model.

This is opt-in live inference, not a pytest suite or a simulated backend.
Requires the project's dev and codemode extras and a POSIX pseudo-terminal.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:80/v1')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    root = (args.output_dir or Path(tempfile.mkdtemp(prefix='openagentic-live-'))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'results.json').exists():
        parser.error('Choose a fresh output directory; previous evidence will not be overwritten.')
    scripts = Path(__file__).parent / 'live_acceptance'
    started = time.monotonic()
    phases = []
    for name in ('cli', 'runtime', 'extension'):
        command = [sys.executable, str(scripts / f'{name}.py')]
        command += ['--root', str(root), '--api-base', args.endpoint] if name == 'cli' else [str(root)]
        completed = subprocess.run(command, check=False)
        phases.append({'phase': name, 'exit_code': completed.returncode})
        if name == 'cli' and not (root / 'results.json').exists():
            break
    cases = []
    model = None
    for filename in ('results.json', 'runtime-results.json', 'extension-results.json'):
        path = root / filename
        if path.exists():
            data = json.loads(path.read_text())
            if filename == 'results.json':
                model = data['model']
                cases.extend(data['cases'])
            else:
                cases.extend(data)
    summary = {'time_utc': datetime.now(timezone.utc).isoformat(), 'endpoint': args.endpoint,
               'model': model, 'duration_seconds': round(time.monotonic()-started, 2),
               'phases': phases, 'cases': cases,
               'passed': bool(cases) and len(phases) == 3 and all(p['exit_code'] == 0 for p in phases)
                         and all(c['passed'] for c in cases)}
    (root / 'live-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': summary['passed'], 'cases': len(cases), 'evidence': str(root)}, ensure_ascii=False))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
