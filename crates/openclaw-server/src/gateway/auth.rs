//! 连接认证实现

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use chrono::Utc;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::gateway::protocol::{
    AuthCredentials, DeviceInfo, ErrorCode, GatewayFrame, Policy, SessionSnapshot, SessionId, RunId, RequestId,
};

const HANDSHAKE_TIMEOUT_SECS: u64 = 10;

pub struct AuthManager {
    sessions: Arc<RwLock<HashMap<String, AuthenticatedSession>>>,
    nonce_store: Arc<RwLock<HashMap<String, Nonce>>>,
}

struct Nonce {
    value: String,
    expires_at: i64,
    used: bool,
}

#[derive(Clone)]
pub struct AuthenticatedSession {
    pub session_id: String,
    pub user_id: Option<String>,
    pub device: DeviceInfo,
    pub connected_at: chrono::DateTime<Utc>,
    pub last_active_at: chrono::DateTime<Utc>,
}

impl AuthManager {
    pub fn new() -> Self {
        Self {
            sessions: Arc::new(RwLock::new(HashMap::new())),
            nonce_store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// 生成连接挑战
    pub async fn generate_challenge(&self) -> GatewayFrame {
        let nonce = generate_nonce();
        let expires_at = (Utc::now() + Duration::from_secs(HANDSHAKE_TIMEOUT_SECS)).timestamp();

        self.nonce_store.write().await.insert(
            nonce.clone(),
            Nonce {
                value: nonce.clone(),
                expires_at,
                used: false,
            },
        );

        GatewayFrame::ConnectChallenge { nonce, expires_at }
    }

    /// 验证认证信息
    pub async fn verify_auth(
        &self,
        nonce: &str,
        credentials: AuthCredentials,
        device: DeviceInfo,
    ) -> Result<AuthenticatedSession, AuthError> {
        // 1. 检查 nonce 是否有效
        let nonce_valid = {
            let nonces = self.nonce_store.read().await;
            matches!(
                nonces.get(nonce),
                Some(n) if !n.used && n.expires_at > Utc::now().timestamp()
            )
        };

        if !nonce_valid {
            return Err(AuthError::InvalidNonce);
        }

        // 2. 标记 nonce 已使用
        {
            let mut nonces = self.nonce_store.write().await;
            if let Some(n) = nonces.get_mut(nonce) {
                n.used = true;
            }
        }

        // 3. 验证凭证
        let user_id = self.verify_credentials(&credentials).await?;

        // 4. 创建会话
        let session_id = Uuid::new_v4().to_string();

        let session = AuthenticatedSession {
            session_id: session_id.clone(),
            user_id,
            device,
            connected_at: Utc::now(),
            last_active_at: Utc::now(),
        };

        // 5. 存储会话
        self.sessions
            .write()
            .await
            .insert(session_id.clone(), session.clone());

        Ok(session)
    }

    /// 验证凭证 (可扩展实现)
    async fn verify_credentials(
        &self,
        credentials: &AuthCredentials,
    ) -> Result<Option<String>, AuthError> {
        if let Some(token) = &credentials.token {
            if !token.is_empty() {
                return Ok(Some(format!("user_{}", &token[..8.min(token.len())])));
            }
        }

        if let Some(api_key) = &credentials.api_key {
            if !api_key.is_empty() {
                return Ok(Some(format!(
                    "user_{}",
                    &api_key[..8.min(api_key.len())]
                )));
            }
        }

        Ok(None)
    }

    /// 获取会话
    pub async fn get_session(&self, session_id: &str) -> Option<AuthenticatedSession> {
        self.sessions.read().await.get(session_id).cloned()
    }

    /// 更新会话活跃时间
    pub async fn touch_session(&self, session_id: &str) {
        if let Some(session) = self.sessions.write().await.get_mut(session_id) {
            session.last_active_at = Utc::now();
        }
    }

    /// 删除会话
    pub async fn remove_session(&self, session_id: &str) {
        self.sessions.write().await.remove(session_id);
    }

    /// 生成 hello-ok 响应
    pub async fn create_hello_ok(&self, session: &AuthenticatedSession) -> GatewayFrame {
        let methods = get_method_names();
        let events = get_event_names();

        let snapshot = SessionSnapshot {
            session_id: session.session_id.clone(),
            user_id: session.user_id.clone(),
            active_runs: vec![],
            capabilities: session.device.capabilities.clone(),
            max_concurrent: 1,
        };

        GatewayFrame::HelloOk {
            session_id: session.session_id.clone(),
            methods,
            events,
            snapshot,
            policy: Policy::default(),
        }
    }

    /// 获取会话数量
    pub async fn session_count(&self) -> usize {
        self.sessions.read().await.len()
    }

    /// 清理过期 nonce
    pub async fn cleanup_nonces(&self) {
        let now = Utc::now().timestamp();
        let mut nonces = self.nonce_store.write().await;
        nonces.retain(|_, v| v.expires_at > now);
    }
}

impl Default for AuthManager {
    fn default() -> Self {
        Self::new()
    }
}

fn generate_nonce() -> String {
    use rand::RngCore;
    let mut rng = rand::thread_rng();
    let mut bytes = vec![0u8; 32];
    rng.fill_bytes(&mut bytes);
    use base64::Engine;
    base64::engine::general_purpose::STANDARD.encode(&bytes)
}

fn get_method_names() -> Vec<String> {
    vec![
        "agent".to_string(),
        "send".to_string(),
        "node.invoke".to_string(),
        "node.event".to_string(),
        "skills.list".to_string(),
        "skills.invoke".to_string(),
        "session.health".to_string(),
    ]
}

fn get_event_names() -> Vec<String> {
    vec![
        "agent.streaming".to_string(),
        "agent.tool_call".to_string(),
        "agent.tool_result".to_string(),
        "agent.progress".to_string(),
        "agent.final".to_string(),
        "agent.error".to_string(),
        "session.closed".to_string(),
    ]
}

#[derive(Debug)]
pub enum AuthError {
    InvalidNonce,
    ExpiredNonce,
    InvalidCredentials,
    Timeout,
}

impl std::fmt::Display for AuthError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AuthError::InvalidNonce => write!(f, "Invalid nonce"),
            AuthError::ExpiredNonce => write!(f, "Expired nonce"),
            AuthError::InvalidCredentials => write!(f, "Invalid credentials"),
            AuthError::Timeout => write!(f, "Authentication timeout"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_credentials() -> AuthCredentials {
        AuthCredentials {
            token: Some("test_token_12345".to_string()),
            api_key: None,
            signature: None,
            timestamp: None,
        }
    }

    fn create_test_device() -> DeviceInfo {
        DeviceInfo {
            device_id: "device_123".to_string(),
            platform: "ios".to_string(),
            app_version: "1.0.0".to_string(),
            capabilities: vec!["voice".to_string(), "camera".to_string()],
        }
    }

    #[tokio::test]
    async fn test_auth_manager_new() {
        let auth = AuthManager::new();
        assert_eq!(auth.session_count().await, 0);
    }

    #[tokio::test]
    async fn test_generate_challenge() {
        let auth = AuthManager::new();
        
        let challenge = auth.generate_challenge().await;
        
        match challenge {
            GatewayFrame::ConnectChallenge { nonce, expires_at } => {
                assert!(!nonce.is_empty());
                assert!(expires_at > Utc::now().timestamp());
            }
            _ => panic!("Expected ConnectChallenge"),
        }
    }

    #[tokio::test]
    async fn test_verify_auth_success() {
        let auth = AuthManager::new();
        
        // 先生成 challenge 获取 nonce
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        // 使用 nonce 验证
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let result = auth.verify_auth(&nonce, credentials, device).await;
        
        assert!(result.is_ok());
        let session = result.unwrap();
        assert!(!session.session_id.is_empty());
    }

    #[tokio::test]
    async fn test_verify_auth_invalid_nonce() {
        let auth = AuthManager::new();
        
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let result = auth.verify_auth("invalid_nonce", credentials, device).await;
        
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_verify_auth_expired_nonce() {
        let auth = AuthManager::new();
        
        // 手动插入一个已过期的 nonce
        let mut expired_nonce = Nonce {
            value: "expired".to_string(),
            expires_at: Utc::now().timestamp() - 100,
            used: false,
        };
        
        auth.nonce_store.write().await.insert(
            "expired".to_string(),
            expired_nonce,
        );
        
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let result = auth.verify_auth("expired", credentials, device).await;
        
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_verify_auth_nonce_already_used() {
        let auth = AuthManager::new();
        
        // 先生成 challenge
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        // 第一次验证成功
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let _ = auth.verify_auth(&nonce, credentials.clone(), device.clone()).await;
        
        // 第二次使用同一个 nonce 应该失败
        let result = auth.verify_auth(&nonce, credentials, device).await;
        
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_get_session() {
        let auth = AuthManager::new();
        
        // 创建会话
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let session = auth.verify_auth(&nonce, credentials, device).await.unwrap();
        let session_id = session.session_id.clone();
        
        // 获取会话
        let retrieved = auth.get_session(&session_id).await;
        
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().session_id, session_id);
    }

    #[tokio::test]
    async fn test_touch_session() {
        let auth = AuthManager::new();
        
        // 创建会话
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let session = auth.verify_auth(&nonce, credentials, device).await.unwrap();
        let session_id = session.session_id.clone();
        
        // 更新活跃时间
        auth.touch_session(&session_id).await;
        
        // 验证已更新
        let updated = auth.get_session(&session_id).await.unwrap();
        assert!(updated.last_active_at >= session.last_active_at);
    }

    #[tokio::test]
    async fn test_remove_session() {
        let auth = AuthManager::new();
        
        // 创建会话
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = create_test_credentials();
        let device = create_test_device();
        
        let session = auth.verify_auth(&nonce, credentials, device).await.unwrap();
        let session_id = session.session_id.clone();
        
        // 删除会话
        auth.remove_session(&session_id).await;
        
        // 验证已删除
        let retrieved = auth.get_session(&session_id).await;
        assert!(retrieved.is_none());
    }

    #[tokio::test]
    async fn test_create_hello_ok() {
        let auth = AuthManager::new();
        
        let session = AuthenticatedSession {
            session_id: "test_session".to_string(),
            user_id: Some("user_123".to_string()),
            device: create_test_device(),
            connected_at: Utc::now(),
            last_active_at: Utc::now(),
        };
        
        let hello_ok = auth.create_hello_ok(&session).await;
        
        match hello_ok {
            GatewayFrame::HelloOk { session_id, methods, events, snapshot, .. } => {
                assert_eq!(session_id, "test_session");
                assert!(!methods.is_empty());
                assert!(!events.is_empty());
                assert!(snapshot.max_concurrent > 0);
            }
            _ => panic!("Expected HelloOk frame"),
        }
    }

    #[tokio::test]
    async fn test_session_count() {
        let auth = AuthManager::new();
        
        assert_eq!(auth.session_count().await, 0);
        
        // 创建多个会话
        for i in 0..3 {
            let challenge = auth.generate_challenge().await;
            let nonce = match challenge {
                GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
                _ => panic!("Expected ConnectChallenge"),
            };
            
            let credentials = AuthCredentials {
                token: Some(format!("token_{}", i)),
                ..Default::default()
            };
            
            let device = create_test_device();
            
            let _ = auth.verify_auth(&nonce, credentials, device).await;
        }
        
        assert_eq!(auth.session_count().await, 3);
    }

    #[tokio::test]
    async fn test_cleanup_nonces() {
        let auth = AuthManager::new();
        
        // 插入过期 nonce
        let expired = Nonce {
            value: "expired_nonce".to_string(),
            expires_at: Utc::now().timestamp() - 100,
            used: false,
        };
        
        auth.nonce_store.write().await.insert(
            "expired_nonce".to_string(),
            expired,
        );
        
        // 插入有效 nonce
        let valid = Nonce {
            value: "valid_nonce".to_string(),
            expires_at: Utc::now().timestamp() + 100,
            used: false,
        };
        
        auth.nonce_store.write().await.insert(
            "valid_nonce".to_string(),
            valid,
        );
        
        auth.cleanup_nonces().await;
        
        let nonces = auth.nonce_store.read().await;
        assert!(!nonces.contains_key("expired_nonce"));
        assert!(nonces.contains_key("valid_nonce"));
    }

    #[tokio::test]
    async fn test_verify_credentials_with_api_key() {
        let auth = AuthManager::new();
        
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        let credentials = AuthCredentials {
            token: None,
            api_key: Some("api_key_12345".to_string()),
            signature: None,
            timestamp: None,
        };
        
        let device = create_test_device();
        
        let result = auth.verify_auth(&nonce, credentials, device).await;
        
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_anonymous_connection() {
        let auth = AuthManager::new();
        
        let challenge = auth.generate_challenge().await;
        let nonce = match challenge {
            GatewayFrame::ConnectChallenge { nonce, .. } => nonce,
            _ => panic!("Expected ConnectChallenge"),
        };
        
        // 空凭证允许匿名
        let credentials = AuthCredentials::default();
        let device = create_test_device();
        
        let result = auth.verify_auth(&nonce, credentials, device).await;
        
        assert!(result.is_ok());
        assert!(result.unwrap().user_id.is_none());
    }
}
