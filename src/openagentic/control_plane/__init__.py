"""模块说明（中文）：`src/openagentic/control_plane/`。

控制面——LLM 生成之外的调度/判定层，与具体渠道解耦。

职责边界：
- 本模块只管「策略」：哪个后端走哪个配额类别、本地挂了升级到谁。
- 配额数值本身归 `openagentic.concurrency` 底座（其设计规定只读裸 ENV，零业务依赖）。
- 未配置 `OPENAGENTIC_CONTROL_PLANE_CONFIG` 时整体不启用，调用方行为与从前完全一致。
"""

from openagentic.control_plane.config import (
    ControlPlaneConfig,
    EscalationConfig,
    TierConfig,
    load_control_plane_config,
)
from openagentic.control_plane.policy import escalation_target, gate_category

__all__ = [
    "ControlPlaneConfig",
    "EscalationConfig",
    "TierConfig",
    "load_control_plane_config",
    "escalation_target",
    "gate_category",
]
