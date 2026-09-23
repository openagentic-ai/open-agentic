"""跨端能力契约：能力属于统一 Application 底座，端只声明接入和设备事件。"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class Capability(StrEnum):
    CHAT = "chat"
    RETRIEVAL = "retrieval"
    WORKFLOW = "workflow"
    OFFICE = "office"
    ANALYTICS = "analytics"

CORE_CAPABILITIES: frozenset[Capability] = frozenset(Capability)

@dataclass(frozen=True)
class EndpointDescriptor:
    endpoint_id: str
    transport: str
    device_events: frozenset[str] = frozenset()

    @property
    def capabilities(self) -> frozenset[Capability]:
        return CORE_CAPABILITIES

ENDPOINTS = (
    EndpointDescriptor("feishu", "im", frozenset({"message", "approval"})),
    EndpointDescriptor("wecom", "im", frozenset({"message", "approval"})),
    EndpointDescriptor("dingtalk", "im", frozenset({"message", "approval"})),
    EndpointDescriptor("web", "gateway", frozenset({"timer", "browser"})),
    EndpointDescriptor("android", "gateway", frozenset({"location", "timer", "notification"})),
    EndpointDescriptor("miniapp", "gateway", frozenset({"message", "timer"})),
    EndpointDescriptor("desktop", "gateway", frozenset({"file", "timer"})),
)

def endpoint_descriptor(endpoint_id: str) -> EndpointDescriptor:
    for endpoint in ENDPOINTS:
        if endpoint.endpoint_id == endpoint_id:
            return endpoint
    raise KeyError(f"unknown endpoint: {endpoint_id}")
