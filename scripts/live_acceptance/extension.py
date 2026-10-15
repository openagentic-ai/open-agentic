"""Load an actual extension, backed by the running MLX HTTP service."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[2]
model = json.loads((root / 'results.json').read_text())['model']
os.environ.update({'OPENAGENTIC_MEMORY_DIR': str(root / 'extension-memory'),
    'OPENAGENTIC_CONTROL_PLANE_CONFIG': '', 'OPENAGENTIC_JEV_ENABLED': '0',
    'CLI_REACT_MAX_ITERATIONS': '5', 'OPENAGENTIC_API_BASE': '',
    'OPENAGENTIC_PERMISSIONS_PATH': str(root / 'permissions.json'),
    'MODEL_PROVIDER_CONFIG_PATH': str(root / 'providers.json'),
    'OPENAGENTIC_LIVE_DIR': str(root), 'OPENAGENTIC_LIVE_MODEL': model,
    'OPENAGENTIC_LIVE_ENDPOINT': json.loads((root / 'results.json').read_text())['endpoint']})
sys.path.insert(0,str(repo / 'src'))

plugin = root / 'live_extension.py'
plugin.write_text('''
import hashlib, os
from pathlib import Path
import httpx
ROOT = Path(os.environ['OPENAGENTIC_LIVE_DIR']).resolve()
def setup(api):
    async def complete(messages, model, **kwargs):
        body = {'model': os.environ['OPENAGENTIC_LIVE_MODEL'], 'messages': messages, 'temperature': 0.1, 'max_tokens': 1600}
        if kwargs.get('tools'):
            body['tools'] = kwargs['tools']
            body['tool_choice'] = 'auto'
        async with httpx.AsyncClient(trust_env=False, timeout=120) as client:
            response = await client.post(os.environ['OPENAGENTIC_LIVE_ENDPOINT'] + '/chat/completions', json=body)
            response.raise_for_status()
            return {'message': response.json()['choices'][0]['message']}
    api.register_provider('live_transport', complete)
    async def checksum(args):
        path = Path(args['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError('Path outside acceptance workspace')
        return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    api.register_tool('local_checksum', 'Compute the actual SHA256 of a local file',
        {'type':'object','properties':{'path':{'type':'string'}},'required':['path']}, checksum, read_only=True)
    async def guard(call):
        if call['name'] in {'write_file','edit_file','delete_file'} and Path(call['arguments'].get('path','')).resolve() == ROOT / 'extension-protected.txt':
            return {**call,'blocked':'LIVE_GUARD_PROTECTED'}
    api.on('tool_call', guard)
    def startup(event):
        (ROOT / 'extension-session-started.txt').write_text(event['session_id'])
    api.on('session_start', startup)
    api.register_command('probe', lambda args: 'EXTENSION_READY')
''')

async def main():
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions
    ext = Extensions()
    ext.load([plugin])
    events, confirmations, results = [], [], []
    async def confirm(title, detail):
        confirmations.append(title)
        return True
    async with AgentSession(model='live_transport/mlx', extensions=ext,
        session_dir=root/'extension-sessions', cwd=root, confirm_fn=confirm,
        on_event=events.append) as session:
        command = await session.command('probe','')
        results.append({'case':'real_extension_load_lifecycle_command','passed':command=='EXTENSION_READY' and (root/'extension-session-started.txt').read_text()==session.id})
        start=time.monotonic()
        answer = await asyncio.wait_for(session.prompt('请调用 local_checksum 工具，计算文件 '+str(root/'source.txt')+' 的 SHA256。最终只回复完整 SHA256，不要使用其他工具。'),180)
        expected=hashlib.sha256((root/'source.txt').read_bytes()).hexdigest()
        results.append({'case':'real_extension_provider_and_custom_tool','passed':expected in answer and any(e['type']=='tool_execution_start' and e['name']=='local_checksum' for e in events) and bool(confirmations), 'seconds':round(time.monotonic()-start,2)})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
        before=len(events)
        before_confirm=len(confirmations)
        alias = str(root/'extension-protected.txt').replace('/private/var/', '/var/', 1)
        answer=await asyncio.wait_for(session.prompt('请只调用 write_file 创建 '+alias+'，内容 TEST。如果收到 LIVE_GUARD_PROTECTED 拒绝，请不要重试或使用替代工具，只回复 GUARD_REFUSED。'),180)
        blocked=any(e['type']=='tool_execution_end' and 'LIVE_GUARD_PROTECTED' in str(e.get('result')) for e in events[before:])
        results.append({'case':'real_extension_blocks_model_write','passed':blocked and not (root/'extension-protected.txt').exists() and len(confirmations)==before_confirm, 'result':answer})
        (root/'extension-transcript.json').write_text(json.dumps(session.messages,ensure_ascii=False,indent=2))
    (root/'extension-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    for result in results:
        print(json.dumps(result,ensure_ascii=False),flush=True)
    if not all(result['passed'] for result in results):
        raise SystemExit(1)

asyncio.run(main())
