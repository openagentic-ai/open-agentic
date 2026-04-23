"""CLI ReAct loop (one user turn: model 鈫?tools until done or cap)."""

from __future__ import annotations

import json
from typing import Any

from openagentic.cli.llm import litellm_chat
from openagentic.cli.tools import TOOLS, execute_tool
from openagentic.config import SETTINGS


async def react_loop(
    user_input: str,
    messages: list[dict[str, Any]],
    model: str,
    api_base: str | None,
    api_key: str | None,
    *,
    platform_api_base: str | None = None,
    platform_user_email: str | None = None,
) -> str:
    """Run the ReAct loop: Thought 鈫?Action 鈫?Observation 鈫?... 鈫?done."""
    base = (platform_api_base or "").strip()
    if base and not (platform_user_email or "").strip():
        msg = (
            "[骞冲彴] 宸查厤缃?OpenAgentic 鏈嶅姟鍦板潃锛屼絾鏈櫥褰曪紝ReAct 浠ｇ悊涓嶄細璋冪敤澶фā鍨嬨€?
            "璇峰厛鎵ц `/login-platform` 瀹屾垚娉ㄥ唽鎴栫櫥褰曪紙涓?LLM 鍘傚晢 Key 鏃犲叧锛夛紝鍐嶅彂浠诲姟銆?
        )
        print(f"\n\033[33m{msg}\033[0m")
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": msg})
        return msg

    messages.append({"role": "user", "content": user_input})

    last_tool_name = ""
    last_result_preview = ""

    max_iter = max(1, SETTINGS.CLI_REACT_MAX_ITERATIONS)

    for i in range(max_iter):
        if max_iter > 10 and i == max_iter - 6:
            print(
                f"\n\033[33m[鎻愮ず] 宸叉帴杩戝崟杞伐鍏峰惊鐜笂闄愶紙{max_iter}锛夛紝"
                "鑻ヤ粛鏃犵粓绛斿皢鑷姩鍋滄骞剁粰鍑烘槑纭鏄庛€俓033[0m"
            )

        resp = await litellm_chat(messages, model, api_base=api_base, api_key=api_key, tools=TOOLS)
        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        thinking = msg.get("thinking", "")

        if thinking:
            lines = thinking.strip().split("\n")
            if len(lines) > 3:
                print(f"  \033[2m[thinking] {lines[0]}... ({len(lines)} lines)\033[0m")
            else:
                for line in lines:
                    print(f"  \033[2m[thinking] {line}\033[0m")

        if not tool_calls:
            if content:
                print(f"\n\033[32m{content}\033[0m")
            messages.append({"role": "assistant", "content": content})
            return content

        assistant_msg = {
            "role": msg["role"],
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        }
        messages.append(assistant_msg)

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)

            print(f"\n  \033[36m[tool: {name}]\033[0m")

            if name == "done":
                summary = args.get("summary", content or "Done.")
                print(f"\n\033[32m{summary}\033[0m")
                tid_done = tc.get("id")
                if not tid_done:
                    raise RuntimeError("妯″瀷杩斿洖鐨?tool_call 缂哄皯 id锛屾棤娉曞鎺?DeepSeek/OpenAI 鍏煎 API")
                messages.append({"role": "tool", "tool_call_id": tid_done, "content": summary})
                return summary

            result = execute_tool(name, args)
            last_tool_name = name
            last_result_preview = (result or "")[:400].replace("\n", " ")
            print(f"  \033[2m{result[:500]}\033[0m")

            tool_msg: dict = {"role": "tool", "content": result}
            tid = tc.get("id")
            if not tid:
                raise RuntimeError("妯″瀷杩斿洖鐨?tool_call 缂哄皯 id锛屾棤娉曞鎺?DeepSeek/OpenAI 鍏煎 API")
            tool_msg["tool_call_id"] = tid
            messages.append(tool_msg)

    conclusion = (
        f"鏈疆銆屾ā鍨?鈫?宸ュ叿銆嶅惊鐜凡杈惧埌涓婇檺锛堝叡 {max_iter} 杞級锛屽凡鑷姩鍋滄锛岄伩鍏嶆寰幆鎴栨棤闄愭秷鑰?token銆俓n\n"
        "**缁撹**锛氭ā鍨嬫湭鍦ㄩ檺鍒跺唴缁欏嚭绾枃鏈粓绛旓紝涔熸湭璋冪敤 `done` 宸ュ叿鏀跺熬锛屽洜姝ゆ棤娉曞垽瀹氫换鍔″凡瀹屾暣瀹屾垚銆俓n"
    )
    if last_tool_name:
        conclusion += f"**鏈€鍚庢墽琛岀殑宸ュ叿**锛歚{last_tool_name}`\n"
    if last_result_preview:
        conclusion += f"**璇ユ杈撳嚭鎽樿锛堟埅鏂級**锛歿last_result_preview}\n"
    conclusion += (
        "\n**寤鸿浣?*锛氣憼 鏌ョ湅涓婃柟鍚勬宸ュ叿杈撳嚭鑷鍒ゆ柇杩涘害锛涒憽 鎶婇渶姹傛媶灏忓悗閲嶈瘯锛?
        "鈶?涓嬩竴鏉℃秷鎭姹傛ā鍨嬨€屽厛鐢ㄤ竴娈佃瘽鎬荤粨褰撳墠杩涘害涓庣己鍙ｏ紝涓嶈缁х画璋冨伐鍏枫€嶃€?
    )
    print(f"\n\033[31m[宸茶揪 ReAct 寰幆涓婇檺]\033[0m\n\033[33m{conclusion}\033[0m")
    messages.append({"role": "assistant", "content": conclusion})
    return conclusion
