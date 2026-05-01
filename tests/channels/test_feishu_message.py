"""飞书消息解析测试：_parse_content, _extract_post_text, _strip_mentions,
_NON_TEXT_REPLIES, 以及 FeishuChannel.parse_message。

对 feishu.py 的纯函数做零 mock 测试；parse_message 需要 mock SDK。
"""

import json

import pytest

from extensions.channels.base import IncomingMessage
from extensions.channels.feishu import (
    _parse_content,
    _extract_post_text,
    _strip_mentions,
    _NON_TEXT_REPLIES,
    FeishuChannel,
    ChannelConfig,
)


# ── _parse_content ───────────────────────────────────────────────────────


def test_parse_content_text_string():
    """content 是 JSON 字符串、含 text 字段。"""
    text, msg_type = _parse_content(json.dumps({"text": "Hello world"}))
    assert msg_type == "text"
    assert text == "Hello world"


def test_parse_content_text_dict():
    """content 已经是 dict。"""
    text, msg_type = _parse_content({"text": "Hello"})
    assert msg_type == "text"
    assert text == "Hello"


def test_parse_content_image():
    text, msg_type = _parse_content(json.dumps({"image_key": "img_xxx"}))
    assert msg_type == "image"
    assert "图片" in text


def test_parse_content_file():
    text, msg_type = _parse_content(json.dumps({"file_key": "file_xxx"}))
    assert msg_type == "file"
    assert "文件" in text


def test_parse_content_media():
    """media 类型需要同时有 image_key + file_key。"""
    text, msg_type = _parse_content(json.dumps({
        "image_key": "img_xxx",
        "file_key": "vid_xxx",
    }))
    assert msg_type == "media"
    assert "视频" in text


def test_parse_content_sticker():
    text, msg_type = _parse_content(json.dumps({"sticker_key": "sticker_xxx"}))
    assert msg_type == "sticker"
    assert "表情包" in text


def test_parse_content_post():
    """post 类型通过 content 字段（包含 blocks 数组）识别。"""
    content = json.dumps({
        "title": "Post Title",
        "content": [[
            {"tag": "text", "text": "Hello"},
            {"tag": "text", "text": " World"},
        ]]
    })
    text, msg_type = _parse_content(content)
    assert msg_type == "post"
    assert "Post Title" in text
    assert "Hello World" in text


def test_parse_content_empty():
    text, msg_type = _parse_content(json.dumps({}))
    assert msg_type == "unknown"
    assert text == ""


def test_parse_content_invalid_json():
    """JSON 解析失败时回退——把原始字符串当 text 返回。"""
    text, msg_type = _parse_content("not json")
    assert msg_type == "text"
    assert text == "not json"


# ── _extract_post_text ───────────────────────────────────────────────────


def test_extract_post_text_normal():
    blocks = [[
        {"tag": "text", "text": "Hello "},
        {"tag": "text", "text": "World"},
        {"tag": "a", "text": "Link", "href": "http://example.com"},
    ]]
    text = _extract_post_text(blocks)
    assert "Hello World" in text
    assert "Link" in text


def test_extract_post_text_empty():
    assert _extract_post_text([]) == ""
    assert _extract_post_text([[]]) == ""


# ── _strip_mentions ──────────────────────────────────────────────────────


def test_strip_mentions_user():
    result = _strip_mentions("@_user_123 你好")
    assert result.strip() == "你好"


def test_strip_mentions_all():
    result = _strip_mentions("@_all 大家")
    assert result.strip() == "大家"


def test_strip_mentions_multiple():
    result = _strip_mentions("@_user_1 @_user_2 hello")
    assert result.strip() == "hello"


def test_strip_mentions_no_mentions():
    assert _strip_mentions("hello world") == "hello world"


def test_strip_mentions_empty():
    assert _strip_mentions("") == ""


# ── _NON_TEXT_REPLIES ────────────────────────────────────────────────────


def test_non_text_replies_has_all_non_text_types():
    """确认当前 _NON_TEXT_REPLIES 覆盖了所有已处理的非文本类型。
    post/unknown 不在其中——走 LLM 处理。
    """
    for msg_type in ["image", "media", "file", "sticker"]:
        assert msg_type in _NON_TEXT_REPLIES, f"missing {msg_type}"
        assert len(_NON_TEXT_REPLIES[msg_type]) > 0


def test_non_text_replies_are_valid_strings():
    """每条自动回复都是合理长度的字符串。"""
    for msg_type, reply in _NON_TEXT_REPLIES.items():
        assert isinstance(reply, str)
        assert len(reply) > 10, f"{msg_type} reply too short"


# ── FeishuChannel.parse_message ──────────────────────────────────────────


class TestParseMessage:
    @pytest.fixture
    def channel(self):
        config = ChannelConfig(
            platform="feishu",
            app_id="test_app_id",
            app_secret="test_secret",
            extra={"verification_token": "test_token"},
        )
        return FeishuChannel(config)

    @pytest.mark.asyncio
    async def test_parse_url_verification(self, channel):
        body = {"type": "url_verification", "challenge": "test_challenge"}
        msg = await channel.parse_message(body)
        assert msg.text == "__url_verification__"
        assert msg.sender_name == "飞书平台"

    @pytest.mark.asyncio
    async def test_parse_non_message_event(self, channel):
        """非消息事件（如 application.bot_menu_v1）返回 __<event_type>__。"""
        body = {
            "header": {"event_type": "application.bot_menu_v1"},
            "event": {},
        }
        msg = await channel.parse_message(body)
        assert msg.text == "__application.bot_menu_v1__"

    @pytest.mark.asyncio
    async def test_parse_text_message_websocket(self, channel):
        """WebSocket 文本消息——header/event 嵌套结构。"""
        body = {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "chat_id": "chat123",
                    "content": json.dumps({"text": "你好"}),
                },
                "sender": {
                    "sender_id": {"user_id": "user123", "open_id": "ou_abc"},
                    "sender_name": "测试用户",
                },
            },
        }
        msg = await channel.parse_message(body)
        assert msg.chat_id == "chat123"
        assert msg.sender_id == "user123"
        assert msg.sender_open_id == "ou_abc"
        assert msg.sender_name == "测试用户"
        assert msg.msg_type == "text"
        assert "你好" in msg.text
        assert msg.platform == "feishu"
