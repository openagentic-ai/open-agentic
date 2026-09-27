"""AI 员工岗位注册表。

岗位是稳定的路由标识；具体 Agent 实例仍由用户按自己的模型、工具和权限创建。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmployeeRole:
    key: str
    department: str
    title: str
    description: str


ROLE_REGISTRY: dict[str, EmployeeRole] = {
    "business_analyst": EmployeeRole("business_analyst", "delivery", "业务落地分析师", "把模糊需求改成可执行任务"),
    "delivery_risk": EmployeeRole("delivery_risk", "delivery", "交付推进与风险员", "跟进进度、依赖和阻塞"),
    "acceptance_retro": EmployeeRole("acceptance_retro", "delivery", "交付验收与复盘员", "按标准验收并沉淀经验"),
    "ai_engineer": EmployeeRole("ai_engineer", "engineering", "AI 系统工程师", "开发和集成 AI 系统"),
    "integration_ops": EmployeeRole("integration_ops", "engineering", "集成运维工程师", "处理部署、权限和链路故障"),
    "quality_review": EmployeeRole("quality_review", "engineering", "技术质量审查员", "测试并检查安全和稳定性"),
    "customer_validation": EmployeeRole("customer_validation", "commercial_knowledge", "客户问题验证员", "验证客户问题和投入价值"),
    "productization": EmployeeRole("productization", "commercial_knowledge", "方案产品化员", "把交付经验变成可复用方案"),
    "knowledge_editor": EmployeeRole("knowledge_editor", "commercial_knowledge", "知识资产编辑", "整理可检索和可复用的知识"),
}


def get_employee_role(key: str) -> EmployeeRole | None:
    """按稳定岗位标识查注册表。"""
    return ROLE_REGISTRY.get(key)
