"""飞书 WebSocket 监听脚本——支持工具调用（run_command / read_file / lark-cli）。"""
import asyncio, logging, signal, sys, os, json, subprocess, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 关掉 litellm 远程 cost map 拉取——走代理每次超时 6 秒
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
# 确保 API 调用直连不过代理
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ["NO_PROXY"] = "*"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from extensions.channels.feishu import try_create_feishu_channel

stop = asyncio.Event()
_chat_histories: dict[str, list[dict]] = {}
MAX_HISTORY = 20
MAX_TOOL_ITERATIONS = 5

# ── 工具定义 ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在服务器上执行终端命令并返回输出。用于运行脚本、查看系统状态、git操作等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取服务器上的文件内容。用于查看代码、配置、日志等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径（绝对路径）"},
                    "max_lines": {"type": "integer", "description": "最大读取行数，默认200"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lark_cli",
            "description": "飞书全能工具，覆盖几乎所有飞书 API。"
                           "将用户意图翻译为 lark-cli 命令参数即可。"
                           "── 日程 ── calendar +agenda(今日日程) / +create(创建) / +update(修改) / +delete(删除) / events instance_view(查询时段内事件)"
                           "── 文档 ── docs +create(创建文档) / +fetch(读内容) / +update(修改) / +search(搜索) / +media-insert(插入图片/文件) / +media-download(下载媒体)"
                           "── 多维表格 ── base +record-list(查记录) / +record-search(搜索) / +record-batch-create(批量创建) / +record-batch-update(批量更新) / +record-delete(删除) / +record-upsert(创建或更新) / +table-create(建表) / +field-create(加字段) / +form-create(创建表单) / +workflow-create(创建工作流) / +dashboard-create(创建仪表盘)"
                           "── 消息 ── im +messages-send(发消息) / +messages-reply(回复) / +chat-create(建群) / +chat-messages-list(查聊天记录) / +chat-search(搜索群) / +messages-search(搜索消息)"
                           "── 审批 ── approval instances(审批实例管理) / tasks(审批任务管理)"
                           "── 通讯录 ── contact +search-user(搜索用户)"
                           "── 云盘 ── drive(文件上传/下载/权限管理)"
                           "── 邮箱 ── mail(邮件读写/草稿/联系人)"
                           "── 任务 ── task(任务/任务列表CRUD)"
                           "── 知识库 ── wiki(空间/节点管理)"
                           "── 表格 ── sheets(电子表格读写)"
                           "── 幻灯片 ── slides(创建/修改/读内容)"
                           "── 会议纪要 ── minutes(搜索/读内容)"
                           "── 视频会议 ── vc +search(搜索会议) / +notes(查询笔记) / +recording(查询录制)——只读"
                           "── 白板 ── whiteboard(创建/编辑)"
                           "── 考勤 ── attendance(查询打卡记录)"
                           "── OKR ── okr(目标/关键结果/对齐)"
                           "── 通用 API ── lark-cli api GET/POST /open-apis/xxx(所有未封装API的兜底)"
                           "⚠️ 不要假设不能做——先用 lark-cli 试试，几乎所有飞书 API 都能调。",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "lark-cli 命令参数，如 [\"calendar\", \"+agenda\"]",
                    },
                },
                "required": ["args"],
            },
        },
    },
]


# ── 工具执行 ──────────────────────────────────────────────────────────

async def execute_tool(name: str, args: dict) -> str:
    """执行工具调用，返回结果字符串。"""
    if name == "run_command":
        return await _run_command(args.get("command", ""))
    elif name == "read_file":
        return await _read_file(args.get("path", ""), args.get("max_lines", 200))
    elif name == "lark_cli":
        return await _run_lark_cli(args.get("args", []))
    return f"未知工具: {name}"


async def _run_command(command: str) -> str:
    cmd = command.strip()
    if not cmd:
        return "错误：命令为空"
    logging.info("[TOOL] run_command: %s", cmd[:200])
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        result = out or err or "(无输出)"
        if len(result) > 4000:
            result = result[:4000] + "\n... (输出截断)"
        return result
    except asyncio.TimeoutError:
        return "错误：命令执行超时 (30s)"


async def _read_file(path: str, max_lines: int = 200) -> str:
    fpath = os.path.expanduser(path)
    logging.info("[TOOL] read_file: %s", fpath)
    # 安全检查：禁止读取敏感系统文件
    dangerous = ["/etc/shadow", "/etc/passwd", "~/.ssh", "id_rsa", ".env", "secret"]
    if any(d in fpath for d in dangerous):
        return "错误：出于安全考虑，禁止读取此文件"
    try:
        if not os.path.isfile(fpath):
            return f"错误：文件不存在 — {fpath}"
        size = os.path.getsize(fpath)
        if size > 2 * 1024 * 1024:
            return f"错误：文件过大 ({size / 1024:.0f}KB)"
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            lines = [next(f) for _ in range(max_lines)]
        return "".join(lines)
    except Exception as e:
        return f"读取失败：{e}"


async def _run_lark_cli(args: list[str]) -> str:
    cmd = ["lark-cli"] + args
    logging.info("[TOOL] lark-cli: %s", " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        result = out or err or "(无输出)"
        if len(result) > 4000:
            result = result[:4000] + "\n... (输出截断)"
        return result
    except asyncio.TimeoutError:
        return "错误：lark-cli 执行超时 (30s)"
    except FileNotFoundError:
        return "错误：lark-cli 未安装"


# ── AI 回复（带工具调用循环）──────────────────────────────────────────

async def ai_reply(user_text: str, chat_id: str) -> str:
    from openagentic.agent.engine import ConversationEngine
    from openagentic.identity import build_system_prompt

    model = os.getenv("OPENAGENTIC_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL", "deepseek/deepseek-v4-flash")
    api_key = os.getenv("OPENAI_API_KEY")
    # 仅 openai/ 前缀的模型走自定义 api_base，其它走 litellm 原生 provider
    api_base = os.getenv("OPENAI_BASE_URL") if model.startswith("openai/") else None

    engine = ConversationEngine(
        model=model, api_key=api_key, api_base=api_base, tools=TOOLS,
        system_prompt=build_system_prompt([
            "当前通过飞书渠道接入。格式限制：飞书卡片不支持 Markdown 表格——遇到表格数据用列表或缩进文本代替，不要用 |---|---| 语法。",
        ]),
        executor=execute_tool,
        max_iterations=MAX_TOOL_ITERATIONS,
    )

    history = _chat_histories.setdefault(chat_id, [])

    messages = [
        {"role": "system", "content": engine.system_prompt},
        *history[-MAX_HISTORY:],
        {"role": "user", "content": user_text},
    ]

    try:
        reply = await engine.chat(messages)
    except Exception as e:
        logging.exception("LLM call failed")
        reply = f"抱歉，AI 调用失败：{e}"

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    _chat_histories[chat_id] = history[-MAX_HISTORY:]
    return reply


# ── 主入口 ────────────────────────────────────────────────────────────

async def main():
    ch = try_create_feishu_channel()
    if not ch:
        logging.error("FAIL: Channel not created — check .env")
        return

    async def callback(msg):
        logging.info(">>> %s: %s", msg.sender_id, msg.text)
        card_id = await ch.send_thinking_card(msg.chat_id)
        reply = await ai_reply(msg.text, msg.chat_id)
        if card_id and reply:
            await ch.update_card(card_id, reply)
        return ""

    ch._ws_stop = stop
    await ch.start(agent_cb=callback)
    logging.info("WebSocket 已启动（工具就绪），等待飞书消息... (Ctrl+C 退出)")
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop.set())
    await stop.wait()
    await ch.stop()
    logging.info("已退出")


asyncio.run(main())
