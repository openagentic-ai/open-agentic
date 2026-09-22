"""GateConfig 类别契约——新增 llm_local（本地推理后端）类别：

1. llm_local 类别存在（否则 acquire("llm_local") 会静默回落到 default=100，比 llm 还宽松）
2. 默认额度按本地 vLLM 序列槽位设定（2），远小于云端 llm 类别（30）
3. 可用 OPENAGENTIC_GATE_LLM_LOCAL_CONCURRENCY 覆盖
"""

from __future__ import annotations

from openagentic.concurrency.config import GateConfig


def test_llm_local_category_exists():
    """缺了这个类别，控制面选它时会静默回落到 default(100)——比 llm(30) 还宽松。"""
    assert "llm_local" in GateConfig().categories


def test_llm_local_default_matches_slot_count():
    """默认对齐 vLLM max_num_seqs=2。"""
    assert GateConfig().categories["llm_local"].concurrency == 2


def test_llm_local_stricter_than_cloud():
    cfg = GateConfig()
    assert cfg.categories["llm_local"].concurrency < cfg.categories["llm"].concurrency


def test_llm_local_concurrency_env_override(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_GATE_LLM_LOCAL_CONCURRENCY", "3")
    assert GateConfig.from_env().categories["llm_local"].concurrency == 3


def test_llm_local_no_rate_limit_by_default():
    """本地后端没有 QPS 概念（不是远程 API），默认不设令牌桶。"""
    assert GateConfig().categories["llm_local"].rate_per_sec is None
