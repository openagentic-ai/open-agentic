//! Gateway 协议帧类型定义

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

pub type RequestId = String;
pub type SessionId = String;

#[derive(Debug, Clone, Serialize, Deserialize, Hash, Eq, PartialEq)]
pub struct RunId(String);

impl RunId {
    pub fn new() -> Self {
        use uuid::Uuid;
        Self(format!("run_{}", Uuid::new_v4()))
    }

    pub fn from_string(s: impl Into<String>) -> Self {
        Self(s.into())
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl Default for RunId {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Display for RunId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::ops::Deref for RunId {
    type Target = String;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload")]
pub enum GatewayFrame {
    // ========== 请求帧 (客户端 -> 网关) ==========

    /// 连接认证
    Connect {
        auth: AuthCredentials,
        device: DeviceInfo,
    },

    /// 方法调用请求
    Request {
        id: RequestId,
        method: String,
        params: serde_json::Value,
        #[serde(skip_serializing_if = "Option::is_none")]
        idempotency_key: Option<String>,
    },

    /// 订阅事件
    Subscribe {
        run_id: RunId,
    },

    /// 取消订阅
    Unsubscribe {
        run_id: RunId,
    },

    // ========== 响应帧 (网关 -> 客户端) ==========

    /// 连接挑战 (nonce)
    ConnectChallenge {
        nonce: String,
        expires_at: i64,
    },

    /// 认证成功 - 会话快照
    HelloOk {
        session_id: SessionId,
        methods: Vec<String>,
        events: Vec<String>,
        snapshot: SessionSnapshot,
        policy: Policy,
    },

    /// 方法调用响应 - 第一阶段：已接受
    Accepted {
        request_id: RequestId,
        run_id: RunId,
        #[serde(skip_serializing_if = "Option::is_none")]
        duplicate_of: Option<RunId>,
    },

    /// 方法调用响应 - 完成时
    Response {
        request_id: RequestId,
        run_id: RunId,
        status: ResponseStatus,
    },

    /// 流式事件
    Event {
        run_id: RunId,
        event_type: EventType,
        seq: u64,
        data: serde_json::Value,
    },

    /// 最终结果
    Final {
        run_id: RunId,
        summary: ExecutionSummary,
    },

    /// 错误
    Error {
        code: ErrorCode,
        message: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        request_id: Option<RequestId>,
        #[serde(skip_serializing_if = "Option::is_none")]
        run_id: Option<RunId>,
    },

    /// 心跳
    Ping {
        timestamp: i64,
    },

    Pong {
        timestamp: i64,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthCredentials {
    pub token: Option<String>,
    pub api_key: Option<String>,
    pub signature: Option<String>,
    pub timestamp: Option<i64>,
}

impl Default for AuthCredentials {
    fn default() -> Self {
        Self {
            token: None,
            api_key: None,
            signature: None,
            timestamp: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub device_id: String,
    pub platform: String,
    pub app_version: String,
    pub capabilities: Vec<String>,
}

impl Default for DeviceInfo {
    fn default() -> Self {
        Self {
            device_id: String::new(),
            platform: "unknown".to_string(),
            app_version: "0.0.0".to_string(),
            capabilities: vec![],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionSnapshot {
    pub session_id: SessionId,
    pub user_id: Option<String>,
    pub active_runs: Vec<RunStatus>,
    pub capabilities: Vec<String>,
    pub max_concurrent: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunStatus {
    pub run_id: RunId,
    pub status: ExecutionStatus,
    pub progress: f32,
    pub started_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ExecutionStatus {
    Pending,
    Accepted,
    Running,
    Streaming,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Policy {
    pub max_request_size_bytes: usize,
    pub max_response_size_bytes: usize,
    pub handshake_timeout_secs: u64,
    pub idle_timeout_secs: u64,
    pub max_concurrent_per_session: usize,
    pub max_concurrent_global: usize,
}

impl Default for Policy {
    fn default() -> Self {
        Self {
            max_request_size_bytes: 10 * 1024 * 1024,
            max_response_size_bytes: 50 * 1024 * 1024,
            handshake_timeout_secs: 10,
            idle_timeout_secs: 300,
            max_concurrent_per_session: 1,
            max_concurrent_global: 10,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionSummary {
    pub run_id: RunId,
    pub status: ExecutionStatus,
    pub output: Option<String>,
    pub tokens_used: Option<u64>,
    pub tool_calls: Vec<ToolCallRecord>,
    pub duration_ms: u64,
    pub error: Option<String>,
    pub completed_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallRecord {
    pub id: String,
    pub name: String,
    pub arguments: serde_json::Value,
    pub result: Option<serde_json::Value>,
    pub started_at: DateTime<Utc>,
    pub duration_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    Streaming,
    ToolCall,
    ToolResult,
    Progress,
    Error,
    Waiting,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ResponseStatus {
    Ok,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    Timeout,
    AuthRequired,
    AuthFailed,
    InvalidMethod,
    InvalidParams,
    RateLimited,
    InternalError,
    PolicyViolation,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MethodDefinition {
    pub name: String,
    pub params_schema: serde_json::Value,
    pub required_idempotency_key: bool,
    pub required_params: Vec<String>,
}

pub fn get_methods() -> Vec<MethodDefinition> {
    vec![
        MethodDefinition {
            name: "agent".to_string(),
            params_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "session_id": { "type": "string" },
                    "message": { "type": "string" },
                    "idempotency_key": { "type": "string" }
                },
                "required": ["message"]
            }),
            required_idempotency_key: true,
            required_params: vec!["message".to_string()],
        },
        MethodDefinition {
            name: "send".to_string(),
            params_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "channel": { "type": "string" },
                    "to": { "type": "string" },
                    "content": { "type": "string" },
                    "idempotency_key": { "type": "string" }
                },
                "required": ["content"]
            }),
            required_idempotency_key: true,
            required_params: vec!["content".to_string()],
        },
        MethodDefinition {
            name: "node.invoke".to_string(),
            params_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "node_id": { "type": "string" },
                    "method": { "type": "string" },
                    "params": { "type": "object" }
                },
                "required": ["node_id", "method"]
            }),
            required_idempotency_key: false,
            required_params: vec![],
        },
    ]
}

pub fn get_events() -> Vec<String> {
    vec![
        "agent.streaming".to_string(),
        "agent.tool_call".to_string(),
        "agent.tool_result".to_string(),
        "agent.progress".to_string(),
        "agent.final".to_string(),
        "agent.error".to_string(),
        "agent.waiting".to_string(),
        "session.health".to_string(),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_id_generation() {
        let run_id = RunId::new();
        assert!(run_id.as_str().starts_with("run_"));
        assert_eq!(run_id.as_str().len(), 40); // "run_" + 36 (uuid)
    }

    #[test]
    fn test_run_id_from_string() {
        let run_id = RunId::from_string("test_run_123");
        assert_eq!(run_id.as_str(), "test_run_123");
    }

    #[test]
    fn test_gateway_frame_serialization() {
        let frame = GatewayFrame::ConnectChallenge {
            nonce: "test_nonce".to_string(),
            expires_at: 1234567890,
        };
        let json = serde_json::to_string(&frame).unwrap();
        assert!(json.contains("ConnectChallenge"));
        assert!(json.contains("test_nonce"));
    }

    #[test]
    fn test_gateway_frame_deserialization() {
        let json = r#"{"type":"ConnectChallenge","payload":{"nonce":"test_nonce","expires_at":1234567890}}"#;
        let frame: GatewayFrame = serde_json::from_str(json).unwrap();
        match frame {
            GatewayFrame::ConnectChallenge { nonce, expires_at } => {
                assert_eq!(nonce, "test_nonce");
                assert_eq!(expires_at, 1234567890);
            }
            _ => panic!("Expected ConnectChallenge"),
        }
    }

    #[test]
    fn test_policy_default() {
        let policy = Policy::default();
        assert_eq!(policy.handshake_timeout_secs, 10);
        assert_eq!(policy.idle_timeout_secs, 300);
        assert_eq!(policy.max_concurrent_global, 10);
    }

    #[test]
    fn test_execution_status_values() {
        use serde_json;
        
        let statuses = vec![
            ExecutionStatus::Pending,
            ExecutionStatus::Accepted,
            ExecutionStatus::Running,
            ExecutionStatus::Streaming,
            ExecutionStatus::Completed,
            ExecutionStatus::Failed,
            ExecutionStatus::Cancelled,
        ];
        
        for status in statuses {
            let json = serde_json::to_string(&status).unwrap();
            let parsed: ExecutionStatus = serde_json::from_str(&json).unwrap();
            assert_eq!(status, parsed);
        }
    }

    #[test]
    fn test_get_methods() {
        let methods = get_methods();
        assert!(!methods.is_empty());
        
        let agent_method = methods.iter().find(|m| m.name == "agent").unwrap();
        assert!(agent_method.required_idempotency_key);
        assert!(agent_method.required_params.contains(&"message".to_string()));
    }

    #[test]
    fn test_get_events() {
        let events = get_events();
        assert!(events.contains(&"agent.streaming".to_string()));
        assert!(events.contains(&"agent.final".to_string()));
    }

    #[test]
    fn test_device_info_default() {
        let device = DeviceInfo::default();
        assert_eq!(device.platform, "unknown");
        assert!(device.capabilities.is_empty());
    }

    #[test]
    fn test_error_code_serialization() {
        let error = GatewayFrame::Error {
            code: ErrorCode::AuthFailed,
            message: "Test error".to_string(),
            request_id: Some("req_123".to_string()),
            run_id: None,
        };
        
        let json = serde_json::to_string(&error).unwrap();
        assert!(json.contains("auth_failed"));
        assert!(json.contains("Test error"));
    }
}
