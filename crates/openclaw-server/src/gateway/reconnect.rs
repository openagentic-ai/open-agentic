//! 重连恢复机制实现

use std::sync::Arc;

use tokio::sync::RwLock;

use crate::gateway::auth::{AuthManager, AuthenticatedSession};
use crate::gateway::protocol::{GatewayFrame, RunId, SessionSnapshot};
use crate::gateway::two_phase::TwoPhaseManager;

pub enum ReconnectAction {
    Snapshot(SessionSnapshot),
    SendFinal { run_id: RunId },
    Resubscribe { run_id: RunId },
    TaskGone { run_id: RunId },
}

pub struct ReconnectManager {
    auth_manager: Arc<AuthManager>,
    two_phase: Arc<TwoPhaseManager>,
}

impl ReconnectManager {
    pub fn new(
        auth_manager: Arc<AuthManager>,
        two_phase: Arc<TwoPhaseManager>,
    ) -> Self {
        Self {
            auth_manager,
            two_phase,
        }
    }

    /// 处理客户端重连
    pub async fn handle_reconnect(
        &self,
        session_id: &str,
        previous_session_id: Option<String>,
    ) -> Result<Vec<ReconnectAction>, ReconnectError> {
        let session = self
            .auth_manager
            .get_session(session_id)
            .await
            .ok_or(ReconnectError::SessionNotFound)?;

        if let Some(prev_id) = previous_session_id {
            return self.recover_from_previous_session(&session, &prev_id).await;
        }

        Ok(vec![ReconnectAction::Snapshot(
            SessionSnapshot {
                session_id: session.session_id.clone(),
                user_id: session.user_id.clone(),
                active_runs: vec![],
                capabilities: session.device.capabilities.clone(),
                max_concurrent: 1,
            },
        )])
    }

    /// 从之前的会话恢复状态
    async fn recover_from_previous_session(
        &self,
        session: &AuthenticatedSession,
        previous_session_id: &str,
    ) -> Result<Vec<ReconnectAction>, ReconnectError> {
        let mut actions = Vec::new();

        let previous_runs = self.get_previous_session_runs(previous_session_id).await;

        for run_id in previous_runs {
            if self.two_phase.get_executing(&run_id).await.is_some() {
                actions.push(ReconnectAction::Resubscribe { run_id });
            } else if self.two_phase.get_completed(&run_id).await.is_some() {
                actions.push(ReconnectAction::SendFinal { run_id });
            } else {
                actions.push(ReconnectAction::TaskGone { run_id });
            }
        }

        actions.push(ReconnectAction::Snapshot(
            SessionSnapshot {
                session_id: session.session_id.clone(),
                user_id: session.user_id.clone(),
                active_runs: vec![],
                capabilities: session.device.capabilities.clone(),
                max_concurrent: 1,
            },
        ));

        Ok(actions)
    }

    async fn get_previous_session_runs(&self, _session_id: &str) -> Vec<RunId> {
        Vec::new()
    }

    /// 获取健康检查信息
    pub async fn get_health_info(&self, session_id: &str) -> Option<HealthInfo> {
        let session = self.auth_manager.get_session(session_id).await?;
        let active_runs = self.two_phase.get_executing_run_ids().await;

        Some(HealthInfo {
            session_id: session.session_id.clone(),
            user_id: session.user_id,
            active_run_count: active_runs.len(),
            global_concurrent: self.two_phase.get_global_concurrent().await,
        })
    }
}

pub struct HealthInfo {
    pub session_id: String,
    pub user_id: Option<String>,
    pub active_run_count: usize,
    pub global_concurrent: usize,
}

#[derive(Debug)]
pub enum ReconnectError {
    SessionNotFound,
    InvalidSession,
}

impl std::fmt::Display for ReconnectError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReconnectError::SessionNotFound => write!(f, "Session not found"),
            ReconnectError::InvalidSession => write!(f, "Invalid session"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_reconnect_manager_new() {
        let auth_manager = Arc::new(AuthManager::new());
        let two_phase = Arc::new(TwoPhaseManager::new(10));
        
        let manager = ReconnectManager::new(auth_manager, two_phase);
        
        assert!(manager.get_health_info("nonexistent").await.is_none());
    }

    #[tokio::test]
    async fn test_handle_reconnect_no_previous() {
        let auth_manager = Arc::new(AuthManager::new());
        let two_phase = Arc::new(TwoPhaseManager::new(10));
        
        // 创建一个会话
        let challenge = auth_manager.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = crate::gateway::protocol::AuthCredentials {
            token: Some("test_token".to_string()),
            ..Default::default()
        };
        
        let device = crate::gateway::protocol::DeviceInfo {
            device_id: "device_123".to_string(),
            platform: "ios".to_string(),
            app_version: "1.0.0".to_string(),
            capabilities: vec![],
        };
        
        let session = auth_manager.verify_auth(&nonce, credentials, device).await.unwrap();
        
        let manager = ReconnectManager::new(auth_manager, two_phase);
        
        let result = manager.handle_reconnect(&session.session_id, None).await;
        
        assert!(result.is_ok());
        let actions = result.unwrap();
        assert!(!actions.is_empty());
    }

    #[tokio::test]
    async fn test_handle_reconnect_session_not_found() {
        let auth_manager = Arc::new(AuthManager::new());
        let two_phase = Arc::new(TwoPhaseManager::new(10));
        
        let manager = ReconnectManager::new(auth_manager, two_phase);
        
        let result = manager.handle_reconnect("nonexistent_session", None).await;
        
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_get_health_info() {
        let auth_manager = Arc::new(AuthManager::new());
        let two_phase = Arc::new(TwoPhaseManager::new(10));
        
        // 创建一个会话
        let challenge = auth_manager.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = crate::gateway::protocol::AuthCredentials {
            token: Some("health_test_token".to_string()),
            ..Default::default()
        };
        
        let device = crate::gateway::protocol::DeviceInfo {
            device_id: "device_456".to_string(),
            platform: "android".to_string(),
            app_version: "2.0.0".to_string(),
            capabilities: vec!["voice".to_string()],
        };
        
        let session = auth_manager.verify_auth(&nonce, credentials, device).await.unwrap();
        
        let manager = ReconnectManager::new(auth_manager, two_phase);
        
        let health = manager.get_health_info(&session.session_id).await;
        
        assert!(health.is_some());
        let h = health.unwrap();
        assert_eq!(h.session_id, session.session_id);
        assert_eq!(h.active_run_count, 0);
    }

    #[tokio::test]
    async fn test_reconnect_action_types() {
        let snapshot = ReconnectAction::Snapshot(SessionSnapshot {
            session_id: "test".to_string(),
            user_id: None,
            active_runs: vec![],
            capabilities: vec![],
            max_concurrent: 1,
        });
        
        match snapshot {
            ReconnectAction::Snapshot(_) => {}
            _ => panic!("Expected Snapshot"),
        }
        
        let send_final = ReconnectAction::SendFinal {
            run_id: RunId::from_string("test_run"),
        };
        
        match send_final {
            ReconnectAction::SendFinal { .. } => {}
            _ => panic!("Expected SendFinal"),
        }
        
        let resubscribe = ReconnectAction::Resubscribe {
            run_id: RunId::from_string("test_run_2"),
        };
        
        match resubscribe {
            ReconnectAction::Resubscribe { .. } => {}
            _ => panic!("Expected Resubscribe"),
        }
        
        let task_gone = ReconnectAction::TaskGone {
            run_id: RunId::from_string("test_run_3"),
        };
        
        match task_gone {
            ReconnectAction::TaskGone { .. } => {}
            _ => panic!("Expected TaskGone"),
        }
    }
}
