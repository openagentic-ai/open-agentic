//! OpenClaw Agent - 多智能体系统
//!
//! 实现 Agent Teams 架构：
//! - 不同类型的 Agent 处理不同任务
//! - Agent Orchestrator 协调多个 Agent
//! - 任务路由和分配机制

// === Public API ===

pub mod agent;
pub mod aieos;
pub mod config;
pub mod orchestrator;
pub mod ports;
pub mod provider;
pub mod sessions;
pub mod sub_agent;
pub mod task;
pub mod team;
pub mod types;

pub use agent::*;
pub use aieos::AIEOS;
pub use config::{AgentDefaults, AgentInstanceConfig, AgentsConfig};
pub use orchestrator::*;
pub use ports::{
    AIPort, MemoryEntry, MemoryPort, RecallItem, SecurityCheckResult, SecurityPort, ToolInfo,
    ToolPort, DevicePort,
};
pub use provider::*;
pub use sessions::*;
pub use sub_agent::*;
pub use task::*;
pub use team::*;
pub use types::*;

pub use openclaw_core::{OpenClawError, Result};

// === Internal (crate-only) ===

pub mod channels;
pub mod decision;
pub mod dependencies;
pub mod device_tool_registry;
pub mod device_tools;
pub mod graph;
pub mod integration;
pub mod memory_pipeline;
pub mod presence;
pub mod real_device_tools;
pub mod router;
pub mod ui_tools;
pub mod voice;

#[cfg(feature = "testing")]
pub mod mock;
