"""飞书卡片工具测试：纯函数，零 mock。

覆盖 extensions/channels/feishu_card_utils.py 全部可测单元：
_build_card, build_thinking_card, build_answer_card,
_sanitize_for_lark_md, _table_to_text, _HEADING_RE, _HR_RE。
"""

import re

from extensions.channels.feishu_card_utils import (
    _build_card,
    build_thinking_card,
    build_answer_card,
    _sanitize_for_lark_md,
    _table_to_text,
    _HEADING_RE,
    _HR_RE,
)


# ── _build_card ──────────────────────────────────────────────────────────


def test_build_card_skeleton():
    card = _build_card([{"tag": "div", "text": "hello"}])
    assert card["config"]["update_multi"] is True
    assert card["header"]["title"]["content"] == "OpenAgentic"
    assert card["header"]["template"] == "wathet"
    elements = card["elements"]
    assert elements[0]["tag"] == "div"
    assert elements[-2]["tag"] == "hr"
    assert elements[-1]["tag"] == "note"
    footer_text = elements[-1]["elements"][0]["content"]
    assert "企业级 AI Agent 平台" in footer_text


def test_build_card_update_multi_false():
    card = _build_card([], update_multi=False)
    assert card["config"]["update_multi"] is False


# ── build_thinking_card ──────────────────────────────────────────────────


def test_build_thinking_card():
    card = build_thinking_card()
    assert card["header"]["title"]["content"] == "OpenAgentic"
    # 含"思考中"占位文本
    elements = card["elements"]
    div = elements[0]
    assert div["tag"] == "div"
    assert div["text"]["content"] == "思考中..."


# ── build_answer_card ────────────────────────────────────────────────────


def test_build_answer_card_plain():
    card = build_answer_card("Hello world")
    elements = card["elements"]
    div = elements[0]
    assert div["tag"] == "div"
    assert "Hello world" in div["text"]["content"]


def test_build_answer_card_markdown():
    card = build_answer_card("**bold** and *italic*")
    content = card["elements"][0]["text"]["content"]
    assert "**bold**" in content
    assert "*italic*" in content


# ── _sanitize_for_lark_md ────────────────────────────────────────────────


def test_sanitize_headings():
    assert _sanitize_for_lark_md("# Title") == "**Title**\n"
    assert _sanitize_for_lark_md("## Sub") == "**Sub**\n"
    assert _sanitize_for_lark_md("### H3") == "**H3**\n"
    assert _sanitize_for_lark_md("###### H6") == "**H6**\n"


def test_sanitize_horizontal_rules():
    assert _sanitize_for_lark_md("---") == ""
    assert _sanitize_for_lark_md("***") == ""
    assert _sanitize_for_lark_md("___") == ""
    assert _sanitize_for_lark_md("-------") == ""


def test_sanitize_code_blocks():
    md = "```\nprint('hello')\n```"
    out = _sanitize_for_lark_md(md)
    assert "```" not in out
    assert "    print('hello')" in out


def test_sanitize_code_blocks_with_language():
    md = "```python\nx = 1\n```"
    out = _sanitize_for_lark_md(md)
    assert "```" not in out
    assert "    x = 1" in out


def test_sanitize_tables():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    out = _sanitize_for_lark_md(md)
    # 管道表头 | 被转为紧凑列表，竖线转分隔符保留在行内
    assert "**A**:" in out
    assert "**B**:" in out
    assert "1" in out and "2" in out


def test_sanitize_mixed_content():
    md = "# Title\n\nSome text\n\n| K | V |\n|---|---|\n| a | b |\n\nMore text"
    out = _sanitize_for_lark_md(md)
    assert "**Title**" in out
    assert "Some text" in out
    assert "**K**:" in out  # 表格已转为 key: value 格式
    assert "a" in out and "b" in out
    assert "More text" in out


def test_sanitize_empty():
    assert _sanitize_for_lark_md("") == ""


def test_sanitize_no_markdown():
    text = "Hello\nWorld"
    assert _sanitize_for_lark_md(text) == "Hello\nWorld"


def test_sanitize_preserves_bold():
    assert _sanitize_for_lark_md("**bold**") == "**bold**"


# ── _table_to_text ───────────────────────────────────────────────────────


def test_table_to_text_standard():
    lines = ["| Name | Age |", "|---|---|", "| Alice | 30 |"]
    out = _table_to_text(lines)
    assert "**Name**: Alice" in out
    assert "**Age**: 30" in out


def test_table_to_text_single_header():
    """仅表头+分隔符，无数据行——回退原样返回。"""
    lines = ["| A | B |", "|---|---|"]
    out = _table_to_text(lines)
    assert out == "\n".join(lines)


def test_table_to_text_mixed_columns():
    """列数不等的行——按实际列处理，超出的 header 用 colN。"""
    lines = ["| A | B |", "|---|---|", "| x |"]
    out = _table_to_text(lines)
    assert "**A**: x" in out


# ── 正则表达式 ───────────────────────────────────────────────────────────


def test_heading_regex():
    assert _HEADING_RE.match("# H1")
    assert _HEADING_RE.match("## H2")
    assert _HEADING_RE.match("###### H6")
    assert _HEADING_RE.match("### 中文标题")
    assert not _HEADING_RE.match("####### H7")  # 最大 6 级
    assert not _HEADING_RE.match("no heading")


def test_hr_regex():
    assert _HR_RE.match("---")
    assert _HR_RE.match("***")
    assert _HR_RE.match("___")
    assert _HR_RE.match("------")
    assert _HR_RE.match("***   ")  # 尾部空格
    assert not _HR_RE.match("--x")
    assert not _HR_RE.match("text")
