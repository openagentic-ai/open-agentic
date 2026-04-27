"""模块说明（中文）：`extensions/channels/feishu_card_utils.py`。

飞书卡片工具：卡片 JSON 构建的唯一入口——feishu.py 不直接拼 JSON。
飞书卡片框架如有 breaking change，只需改这一处。
"""

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
    """构建含答案的卡片。"""
    return _build_card([
        {"tag": "div", "text": {"tag": "lark_md", "content": markdown}},
    ])
