"""Actual SDK/RPC calls to the running local MLX model."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(sys.argv[1]).resolve()
REPO = Path(__file__).resolve().parents[2]
MODEL = json.loads((ROOT / 'results.json').read_text())['model']
BASE = json.loads((ROOT / 'results.json').read_text())['endpoint']
os.environ.update({
    'OPENAGENTIC_MEMORY_DIR': str(ROOT / 'runtime-memory'),
    'OPENAGENTIC_CONTROL_PLANE_CONFIG': '', 'OPENAGENTIC_JEV_ENABLED': '0',
    'OPENAGENTIC_API_BASE': '', 'CLI_REACT_MAX_ITERATIONS': '6',
    'MODEL_PROVIDER_CONFIG_PATH': str(ROOT / 'providers.json'),
    'OPENAGENTIC_PERMISSIONS_PATH': str(ROOT / 'permissions.json'),
    'OPENAGENTIC_CLI_SESSION_DIR': str(ROOT / 'rpc-sessions'),
    'OPENAGENTIC_BASE_URL': BASE, 'OPENAGENTIC_AUTH_TOKEN': 'local',
    'OPENAGENTIC_MODEL': 'local/' + MODEL, 'APP_LOG_LEVEL': 'ERROR',
})
sys.path.insert(0, str(REPO / 'src'))

RESULTS = []


def record(case, passed, **detail):
    result = {'case': case, 'passed': bool(passed), **detail}
    RESULTS.append(result)
    (ROOT / 'runtime-results.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False), flush=True)


async def sdk_steering():
    from openagentic.runtime.agent import AgentSession
    events = []
    started = asyncio.Event()
    def event(value):
        events.append(value)
        if value['type'] == 'agent_start':
            started.set()
    async with AgentSession(model='local/' + MODEL, api_base=BASE, api_key='local',
        session_dir=ROOT / 'sdk-sessions', cwd=ROOT, on_event=event) as session:
        start = time.monotonic()
        task = asyncio.create_task(session.prompt('请实际读取文件 ' + str(ROOT / 'source.txt') + '，然后解释内容。'))
        await started.wait()
        await asyncio.sleep(1)
        busy_when_sent = session.busy and not task.done()
        session.steer('更正当前任务：完成当前工具批次后，只回复 STEER_REAL_OK，不要再调用工具。')
        session.follow_up('这是新的独立后续任务，请只回复 FOLLOW_REAL_OK，不要调用工具。')
        answer = await asyncio.wait_for(task, 240)
        steer_index = next((i for i, m in enumerate(session.messages) if m['role'] == 'assistant' and 'STEER_REAL_OK' in (m.get('content') or '')), -1)
        follow_index = next((i for i, m in enumerate(session.messages) if m['role'] == 'user' and '独立后续任务' in (m.get('content') or '')), -1)
        record('real_sdk_steering_followup', busy_when_sent and steer_index >= 0 and follow_index > steer_index and 'FOLLOW_REAL_OK' in answer,
            seconds=round(time.monotonic()-start,2), busy_when_sent=busy_when_sent,
            assistant_replies=[m.get('content') for m in session.messages if m['role']=='assistant' and not m.get('tool_calls')],
            tool_events=[e['name'] for e in events if e['type']=='tool_execution_start'])
        (ROOT / 'sdk-transcript.json').write_text(json.dumps(session.messages, ensure_ascii=False, indent=2))


async def rpc_codemode():
    (ROOT / 'numbers.json').write_text('[17, 24, 9]')
    env = {**os.environ, 'PYTHONPATH': str(REPO / 'src')}
    stderr = (ROOT / 'rpc-stderr.log').open('w')
    process = await asyncio.create_subprocess_exec(str(REPO / '.venv/bin/python'), '-m', 'openagentic.cli',
        '--mode', 'rpc', '--provider', 'local', '--model', 'local/' + MODEL, '--codemode',
        cwd=str(ROOT), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr)
    events = []
    trace = (ROOT / 'rpc-wire.jsonl').open('w')
    async def request(rid, method, **params):
        process.stdin.write((json.dumps({'id':rid,'method':method,'params':params},ensure_ascii=False)+'\n').encode())
        await process.stdin.drain()
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), 180)
            if not line:
                raise RuntimeError('RPC process ended before response')
            trace.write(line.decode())
            trace.flush()
            value = json.loads(line)
            if 'event' in value:
                events.append(value['event'])
            if value.get('id') == rid:
                return value
    try:
        start = time.monotonic()
        answer = await request(1, 'prompt', text='必须调用 codemode 工具完成：读取当前目录 numbers.json，将其中数字相加。用 JavaScript 的 tools.read_file 读取，用 JSON.parse 和 reduce 计算。不要使用其他顶层工具。最终只回复计算结果。')
        names = [e['name'] for e in events if e['type']=='tool_execution_start']
        record('real_rpc_model_codemode', 'error' not in answer and str(answer.get('result','')).strip()=='50' and 'codemode' in names,
               seconds=round(time.monotonic()-start,2), result=answer, tools=names)
        target = ROOT / 'rpc-protected.txt'
        before = len(events)
        answer = await request(2, 'prompt', text='请只调用 write_file，创建 rpc-protected.txt，内容为 TEST。若工具被拒绝，不要重试或改用其他工具，回复 WRITE_REFUSED。')
        denials = [e for e in events[before:] if e['type']=='tool_execution_end' and '[REFUSED]' in str(e.get('result'))]
        record('real_rpc_write_permission', not target.exists() and bool(denials), result=answer,
               file_created=target.exists(), denied_tools=[e['name'] for e in denials])
        await request(3,'close')
        code = await asyncio.wait_for(process.wait(),10)
        record('real_rpc_clean_exit', code==0, exit_code=code)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        stderr.close()
        trace.close()


async def main():
    try:
        await sdk_steering()
        await rpc_codemode()
    except Exception as exc:
        record('runtime_execution_error', False, error=str(exc))
        raise


asyncio.run(main())

if not all(result['passed'] for result in RESULTS):
    raise SystemExit(1)
