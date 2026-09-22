"""知识库召回 + Jev 精排契约。

分工（2026-09-23 定的）：
- **召回由代码做**：n-gram ILIKE。中文没空格，整句 ILIKE 匹配不上，n-gram 片段才能落到文档里
- **精排由 Jev 做**：逐条判相关性，返回校准概率。这是 embedding 原本干的「语义匹配」，
  但 Jev 判得更好（校准概率 vs 余弦距离），且不需要向量模型、不需要维度对齐

明确的边界：**代码召回是字面匹配，语义相近但用词不同的会漏召**——
Jev 只能从召回到的候选里挑，挑不出没被召回的。
"""

from __future__ import annotations

import pytest

from openagentic.retrieval import knowledge as kb


# --- n-gram 提取（纯函数）--------------------------------------------

def test_ngram_splits_chinese():
    terms = kb.ngram_terms("如何部署服务")
    assert "如何" in terms
    assert "部署" in terms
    assert "服务" in terms


def test_ngram_ignores_punctuation_and_spaces():
    terms = kb.ngram_terms("部署, 服务！")
    assert "部署" in terms and "服务" in terms
    assert "," not in terms and " " not in terms


def test_ngram_dedupes_and_keeps_order():
    terms = kb.ngram_terms("部署部署服务")
    assert len(terms) == len(set(terms)), "不该有重复"
    assert terms[0] == "部署"


def test_ngram_handles_short_query():
    assert kb.ngram_terms("部") == ["部"]
    assert kb.ngram_terms("") == []


def test_ngram_mixes_latin_and_chinese():
    terms = kb.ngram_terms("systemd 重启")
    # 2-gram 下拉丁词只会被切成片段（sy / ys / st ...），不会整词出现
    assert any(t in "systemd" for t in terms), f"应提取出拉丁词片段: {terms}"
    assert "重启" in terms


# --- 精排 -------------------------------------------------------------

class _FakeJev:
    def __init__(self, answers=None, fail=False):
        self._answers = answers
        self.fail = fail
        self.calls: list[dict] = []

    def ask(self, state, questions, max_retries=None):
        self.calls.append({"state": state, "questions": questions})
        if self.fail:
            raise OSError("jev down")
        return self._answers


def _candidates(n: int):
    from openagentic.retrieval import Chunk
    return [Chunk(source="knowledge", text=f"片段{i}", score=1.0, title=f"d{i}") for i in range(n)]


async def test_rerank_keeps_relevant_only(monkeypatch):
    """相关性判定是精排的全部意义：把召回来的噪音滤掉。"""
    jev = _FakeJev({
        "c0": {"type": "noul", "noul": 0.95},
        "c1": {"type": "noul", "noul": 0.05},
        "c2": {"type": "noul", "noul": 0.80},
    })
    kept = await kb.rerank("问题", _candidates(3), jev=jev)
    assert [c.text for c in kept] == ["片段0", "片段2"]


async def test_rerank_batches_by_window(monkeypatch):
    """RLCD 窗口小——候选要分批 fan-out，不是一次全塞。"""
    jev = _FakeJev({f"c{i}": {"type": "noul", "noul": 0.9} for i in range(10)})
    await kb.rerank("问题", _candidates(10), jev=jev, batch_size=4)
    assert len(jev.calls) == 3, f"10 条按 4 条一批应为 3 批，实际 {len(jev.calls)}"


async def test_rerank_fails_open_when_jev_down():
    """精排失败不能把召回结果也弄丢——降级返回原候选。"""
    jev = _FakeJev(fail=True)
    kept = await kb.rerank("问题", _candidates(3), jev=jev)
    assert len(kept) == 3


async def test_rerank_no_jev_returns_candidates():
    kept = await kb.rerank("问题", _candidates(2), jev=None)
    assert len(kept) == 2


async def test_rerank_empty_candidates_skips_jev():
    jev = _FakeJev({})
    assert await kb.rerank("问题", [], jev=jev) == []
    assert jev.calls == []


async def test_rerank_keeps_original_score_as_relevance(monkeypatch):
    """精排后的 score 应换成 Jev 的校准概率——那才是真正的相关性信号。"""
    jev = _FakeJev({"c0": {"type": "noul", "noul": 0.77}})
    kept = await kb.rerank("问题", _candidates(1), jev=jev)
    assert kept[0].score == pytest.approx(0.77)
