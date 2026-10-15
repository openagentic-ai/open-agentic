"""Exercise the actual CLI and local model; no patched functions or fake replies."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

import httpx
import pexpect

REPO = Path(__file__).resolve().parents[2]
PYTHON = REPO / '.venv/bin/python'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root')
    parser.add_argument('--api-base', default='http://127.0.0.1:80/v1')
    args = parser.parse_args()
    root = (Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix='openagentic-live-'))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'artifacts': str(root)}, ensure_ascii=False), flush=True)
    base = args.api_base.rstrip("/")
    with httpx.Client(trust_env=False, timeout=5) as client:
        model = client.get(base + '/models').json()['data'][0]['id']
    runtime_model = 'local/' + model
    config = root / 'providers.json'
    config.write_text(json.dumps({'default_model': runtime_model, 'profiles': [{
        'id': 'local', 'display_name': 'Actual local MLX', 'api_base': base,
        'api_key': 'local', 'models': [runtime_model], 'enabled': True,
    }]}))
    permissions = root / 'permissions.json'
    permissions.write_text(json.dumps({'tools': {
        'read_file': {'policy': 'allow'}, 'run_command': {'policy': 'deny'},
        'write_file': {'policy': 'ask'}, 'delete_file': {'policy': 'deny'},
    }}))
    env = {**os.environ, 'PYTHONPATH': str(REPO / 'src'), 'TERM': 'xterm-256color',
        'PROMPT_TOOLKIT_NO_CPR': '1', 'MODEL_PROVIDER_CONFIG_PATH': str(config),
        'OPENAGENTIC_CLI_SESSION_DIR': str(root / 'sessions'),
        'OPENAGENTIC_MEMORY_DIR': str(root / 'memory'), 'OPENAGENTIC_OBSIDIAN_ROOT': '',
        'OPENAGENTIC_PERMISSIONS_PATH': str(permissions), 'OPENAGENTIC_CONTROL_PLANE_CONFIG': '',
        'OPENAGENTIC_JEV_ENABLED': '0', 'OPENAGENTIC_API_BASE': '',
        'OPENAGENTIC_BASE_URL': base, 'OPENAGENTIC_AUTH_TOKEN': 'local',
        'OPENAGENTIC_MODEL': runtime_model, 'OPENAI_API_KEY': '', 'OPENAI_BASE_URL': '',
        'OPENAI_CHAT_MODEL': '', 'CLI_REACT_MAX_ITERATIONS': '6', 'APP_LOG_LEVEL': 'ERROR'}
    db_path = root / 'sessions/cli.sqlite3'
    results = []
    child = None
    log = None

    def record(name, passed, **detail):
        result = {'case': name, 'passed': bool(passed), **detail}
        results.append(result)
        (root / 'results.json').write_text(json.dumps({'model': model, 'endpoint': base, 'cases': results}, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False), flush=True)

    def state():
        if not db_path.exists():
            return None, None, []
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
            sid, head = db.execute('SELECT id, head FROM sessions ORDER BY rowid DESC LIMIT 1').fetchone()
            node, entries = head, []
            while node is not None:
                parent, kind, data = db.execute('SELECT parent, kind, data FROM entries WHERE id=?', (node,)).fetchone()
                entries.append((kind, json.loads(data)))
                if kind == 'context':
                    break
                node = parent
            messages = []
            for kind, data in reversed(entries):
                if kind == 'context':
                    messages = data
                else:
                    messages.append(data)
        return sid, head, messages

    def start(resume=False):
        nonlocal child, log
        command = [str(PYTHON), '-m', 'openagentic.cli', '--provider', 'local', '--no-provider-check']
        if resume:
            command.append('--continue')
        log = (root / ('terminal-resume.log' if resume else 'terminal.log')).open('w')
        child = pexpect.spawn(command[0], command[1:], cwd=str(root), env=env,
                              encoding='utf-8', timeout=180, dimensions=(35, 130))
        child.logfile_read = log
        child.expect('❯')
        child.sendline('/automodel off')
        child.expect('automodel OFF')

    def wait_turn(old_head, confirmation=None, timeout=180):
        started = time.monotonic()
        output, confirmed = '', False
        while time.monotonic() - started < timeout:
            try:
                output += child.read_nonblocking(8192, timeout=0.1)
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                raise RuntimeError('CLI exited during task: ' + output[-1000:])
            if 'Confirm? (Y/N):' in output and not confirmed:
                if confirmation is None:
                    raise RuntimeError('Unexpected confirmation: ' + output[-1000:])
                # Only approve effects inside the disposable acceptance workspace.
                history = state()[2]
                batch = next((m.get('tool_calls', []) for m in reversed(history)
                              if m.get('role') == 'assistant' and m.get('tool_calls')), [])
                for tool in batch:
                    arguments = tool['function']['arguments']
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    raw_path = arguments.get('path')
                    if raw_path:
                        path = Path(raw_path)
                        path = (path if path.is_absolute() else root / path).resolve()
                        if not path.is_relative_to(root):
                            child.sendline('n')
                            raise RuntimeError('Refused write outside acceptance workspace')
                child.sendline(confirmation)
                confirmed = True
            sid, head, messages = state()
            if head != old_head and messages:
                last = messages[-1]
                finished = (last.get('role') == 'assistant' and not last.get('tool_calls'))
                if last.get('role') == 'tool':
                    done_ids = {tc.get('id') for m in messages if m.get('role') == 'assistant'
                                for tc in m.get('tool_calls', []) if tc.get('function', {}).get('name') == 'done'}
                    finished = last.get('tool_call_id') in done_ids
                if finished:
                    time.sleep(0.3)
                    return messages, round(time.monotonic() - started, 2), confirmed
            if 'Error:' in output:
                raise RuntimeError(output[-1200:])
        raise TimeoutError('CLI task timed out: ' + output[-1200:])

    def turn(prompt, confirmation=None):
        old = state()[1]
        child.sendline(prompt)
        return wait_turn(old, confirmation)

    def stop():
        child.sendline('/exit')
        child.expect('Bye!')
        child.expect(pexpect.EOF)
        child.close()
        log.close()
        if child.exitstatus != 0:
            raise RuntimeError('CLI exit status: ' + str(child.exitstatus))

    def calls(messages):
        return [t['function']['name'] for m in messages for t in m.get('tool_calls', [])]

    nonce = 'LOCAL_' + uuid.uuid4().hex[:16]
    (root / 'source.txt').write_text('verification_code=' + nonce + '\n')
    target = root / 'settings.py'
    target.write_text('limit = 3\nmode = "draft"\n')
    try:
        start()
        messages, elapsed, _ = turn('你好。请只回复 LOCAL_HELLO_OK，不要调用工具。')
        greeting_head = state()[1]
        record('real_cli_greeting', 'LOCAL_HELLO_OK' in str(messages[-1].get('content')), seconds=elapsed, tools=calls(messages))
        old_len = len(messages)
        messages, elapsed, _ = turn('请实际调用 read_file 读取当前目录 source.txt，告诉我 verification_code 的完整值。不要猜测，不要使用 run_command。')
        record('real_cli_read_file', nonce in str(messages[-1].get('content')) and 'read_file' in calls(messages[old_len:]), seconds=elapsed, tools=calls(messages[old_len:]))
        old_len = len(messages)
        messages, elapsed, confirmed = turn('先 read_file 读取 settings.py，再用 edit_file 将 limit = 3 精确替换成 limit = 7，保持其他内容不变。不要使用 write_file 或 run_command。完成后回复 EDIT_OK。', 'y')
        record('real_cli_edit_confirm', target.read_text() == 'limit = 7\nmode = "draft"\n' and confirmed and 'edit_file' in calls(messages[old_len:]), seconds=elapsed, tools=calls(messages[old_len:]), actual=target.read_text())
        old_len = len(messages)
        messages, elapsed, confirmed = turn('用 edit_file 将 settings.py 里的 limit = 7 改为 limit = 99。若用户拒绝，立即停止，不要重试或改用其他工具，并回复 DENIED_OK。', 'n')
        record('real_cli_reject_edit', target.read_text() == 'limit = 7\nmode = "draft"\n' and confirmed and any('[REFUSED]' in str(m.get('content')) for m in messages[old_len:]), seconds=elapsed, tools=calls(messages[old_len:]), actual=target.read_text())
        sid, original_head, _ = state()
        stop()
        start(resume=True)
        messages, elapsed, _ = turn('之前你读取 source.txt 得到的 verification_code 完整值是什么？只根据对话历史回答，不要调用工具。')
        record('real_cli_resume_memory', nonce in str(messages[-1].get('content')), seconds=elapsed, same_session=state()[0] == sid)
        child.sendline('/tree ' + str(greeting_head))
        child.expect('已切换到节点')
        messages, elapsed, _ = turn('只根据当前对话历史判断：你是否已经读取过 source.txt？如果没有，请只回复 NO_PRIOR_CODE。不要调用工具。')
        with sqlite3.connect(db_path) as db:
            branch_retained = db.execute('SELECT COUNT(*) FROM entries WHERE id=?', (original_head,)).fetchone()[0] == 1
        record('real_cli_branch_isolation', 'NO_PRIOR_CODE' in str(messages[-1].get('content')) and not any(nonce in str(m.get('content')) for m in messages) and branch_retained, seconds=elapsed, original_branch_retained=branch_retained)
        stop()
    except Exception as exc:
        record('execution_error', False, error=str(exc))
        if child and child.isalive():
            child.terminate(force=True)
        if log:
            log.close()
        raise
    print(json.dumps({'passed': sum(r['passed'] for r in results), 'total': len(results), 'artifacts': str(root)}, ensure_ascii=False), flush=True)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
