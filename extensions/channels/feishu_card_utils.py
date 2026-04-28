"""模块说明（中文）：`extensions/channels/feishu_card_utils.py`。

飞书卡片工具：卡片 JSON 构建的唯一入口——feishu.py 不直接拼 JSON。
飞书卡片框架如有 breaking change，只需改这一处。
"""

import re

# 卡片 footer 文案
_CARD_FOOTER = "企业级 AI Agent 平台 · 可私有化部署"
_CARD_TITLE = "OpenAgentic"


def _build_card(elements: list[dict], *, update_multi: bool = True) -> dict:
    """构建飞书交互卡片的基础骨架。"""
    return {
        "config": {"update_multi": update_multi},
        "header": {
            "title": {"tag": "plain_text", "content": _CARD_TITLE},
            "template": "wathet",
        },
        "elements": elements + [
            {"tag": "hr"},
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": _CARD_FOOTER}
            ]},
        ],
    }


def build_thinking_card() -> dict:
    """构建"思考中"占位卡片。"""
    return _build_card([
        {"tag": "div", "text": {"tag": "lark_md", "content": "思考中..."}},
    ])


def build_answer_card(markdown: str) -> dict:
    """构建含答案的卡片——自动清理 lark_md 不支持的格式。

    飞书 lark_md 限制：不支持 Markdown 表格（|...|）和围栏代码块（```）。
    此函数做兜底清理——但 LLM 应通过 prompt 避免输出这些格式。
    """
    content = _sanitize_for_lark_md(markdown)
    return _build_card([
        {"tag": "div", "text": {"tag": "lark_md", "content": content}},
    ])


def _sanitize_for_lark_md(md: str) -> str:
    """清理 Markdown 中 lark_md 不支持的语法。

    - 表格 → 紧凑列表格式
    - 围栏代码块 → 缩进文本
    """
    lines = md.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 检测表格开始（当前行是表头，下一行是分隔符）
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\|[\s\-:|]+\|$", lines[i + 1].strip()
        ):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            result.append(_table_to_text(table_lines))
            result.append("")
            continue
        # 检测代码块
        if line.strip().startswith("```"):
            code_lines = []
            i += 1  # 跳过 ```
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 跳过结束的 ```
            for cl in code_lines:
                result.append(f"    {cl}")
            result.append("")
            continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _table_to_text(lines: list[str]) -> str:
    """将 Markdown 表格转为紧凑列表文本。"""
    # 过滤分隔行
    data = [l for l in lines if not re.match(r"^\|[\s\-:|]+\|$", l)]
    if len(data) < 2:
        return "\n".join(lines)

    headers = [c.strip() for c in data[0].strip().strip("|").split("|")]
    out = []
    for row_line in data[1:]:
        cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
        parts = []
        for j, cell in enumerate(cells):
            h = headers[j] if j < len(headers) else f"col{j}"
            parts.append(f"**{h}**: {cell}")
        out.append("- " + " | ".join(parts))
    return "\n".join(out)
