//! Gateway 模块
//!
//! 提供 WebSocket 网关功能，包括：
//! - 协议帧类型定义
//! - 两阶段协议
//! - 幂等去重
//! - 连接认证
//! - 重连恢复

pub mod protocol;
pub mod two_phase;
pub mod deduplicate;
pub mod auth;
pub mod reconnect;

pub use protocol::GatewayFrame;
pub use two_phase::{TwoPhaseManager, JobRequest, AcceptedResult, AcceptError, ExecutingJob};
pub use deduplicate::DeduplicationLayer;
pub use auth::{AuthManager, AuthenticatedSession, AuthError};
pub use reconnect::{ReconnectManager, ReconnectAction, HealthInfo, ReconnectError};

use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::RwLock as AsyncRwLock;

pub struct GatewayState {
    pub auth_manager: Arc<AuthManager>,
    pub two_phase: Arc<TwoPhaseManager>,
    pub deduplication: Arc<DeduplicationLayer>,
    pub sessions: Arc<AsyncRwLock<HashMap<String, SessionState>>>,
}

pub struct SessionState {
    pub session: AuthenticatedSession,
    pub sender: tokio::sync::mpsc::Sender<GatewayFrame>,
}

impl GatewayState {
    pub fn new(max_global_concurrent: usize) -> Self {
        Self {
            auth_manager: Arc::new(AuthManager::new()),
            two_phase: Arc::new(TwoPhaseManager::new(max_global_concurrent)),
            deduplication: Arc::new(DeduplicationLayer::new()),
            sessions: Arc::new(AsyncRwLock::new(HashMap::new())),
        }
    }

    pub fn with_reconnect_manager(&self) -> ReconnectManager {
        ReconnectManager::new(
            self.auth_manager.clone(),
            self.two_phase.clone(),
        )
    }
}

impl Default for GatewayState {
    fn default() -> Self {
        Self::new(10)
    }
}
