//! 两阶段协议实现

use std::collections::HashMap;
use std::sync::Arc;

use chrono::{Duration, Utc};
use tokio::sync::{mpsc, RwLock};

use crate::gateway::protocol::{
    ErrorCode, EventType, ExecutionStatus, ExecutionSummary, GatewayFrame, RunId,
};

pub struct TwoPhaseManager {
    pending: Arc<RwLock<HashMap<RunId, PendingJob>>>,
    executing: Arc<RwLock<HashMap<RunId, ExecutingJob>>>,
    completed: Arc<RwLock<HashMap<String, CachedResult>>>,
    global_concurrent: Arc<RwLock<usize>>,
    max_global_concurrent: usize,
}

struct PendingJob {
    run_id: RunId,
    request: JobRequest,
    accepted_at: chrono::DateTime<Utc>,
}

#[derive(Clone)]
pub struct ExecutingJob {
    run_id: RunId,
    request: JobRequest,
    sender: mpsc::Sender<GatewayFrame>,
    started_at: chrono::DateTime<Utc>,
    seq: u64,
}

#[derive(Clone)]
pub struct JobRequest {
    pub method: String,
    pub params: serde_json::Value,
    pub idempotency_key: Option<String>,
    pub session_id: String,
    pub max_concurrent: usize,
}

#[derive(Clone)]
pub struct CachedResult {
    pub run_id: RunId,
    pub summary: ExecutionSummary,
    pub idempotency_key: String,
    pub cached_at: chrono::DateTime<Utc>,
}

pub struct AcceptedResult {
    pub run_id: RunId,
    pub duplicate_of: Option<RunId>,
    pub cached_summary: Option<ExecutionSummary>,
}

#[derive(Debug)]
pub enum AcceptError {
    RateLimited { message: String },
    InvalidParams { message: String },
    InternalError { message: String },
}

impl std::fmt::Display for AcceptError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AcceptError::RateLimited { message } => write!(f, "Rate limited: {}", message),
            AcceptError::InvalidParams { message } => write!(f, "Invalid params: {}", message),
            AcceptError::InternalError { message } => write!(f, "Internal error: {}", message),
        }
    }
}

impl TwoPhaseManager {
    pub fn new(max_global_concurrent: usize) -> Self {
        Self {
            pending: Arc::new(RwLock::new(HashMap::new())),
            executing: Arc::new(RwLock::new(HashMap::new())),
            completed: Arc::new(RwLock::new(HashMap::new())),
            global_concurrent: Arc::new(RwLock::new(0)),
            max_global_concurrent,
        }
    }

    /// 阶段1: 接受请求，立即返回 runId
    pub async fn accept(
        &self,
        request: JobRequest,
        response_sender: mpsc::Sender<GatewayFrame>,
    ) -> Result<AcceptedResult, AcceptError> {
        // 1. 检查幂等键 - 如果已有缓存结果，直接返回
        if let Some(key) = &request.idempotency_key {
            // 检查已完成缓存
            if let Some(cached) = self.get_cached(key).await {
                return Ok(AcceptedResult {
                    run_id: cached.run_id.clone(),
                    duplicate_of: Some(cached.run_id.clone()),
                    cached_summary: Some(cached.summary.clone()),
                });
            }
            // 检查正在执行的任务
            if let Some(executing) = self.executing.read().await.values().find(|j| j.request.idempotency_key.as_ref() == Some(key)) {
                return Ok(AcceptedResult {
                    run_id: executing.run_id.clone(),
                    duplicate_of: Some(executing.run_id.clone()),
                    cached_summary: None,
                });
            }
        }

        // 2. 检查并发限制
        let global_count = *self.global_concurrent.read().await;
        if global_count >= self.max_global_concurrent {
            return Err(AcceptError::RateLimited {
                message: "Global concurrent limit reached".to_string(),
            });
        }

        // 3. 创建 runId 并注册为 pending
        let run_id = RunId::new();

        let pending = PendingJob {
            run_id: run_id.clone(),
            request: request.clone(),
            accepted_at: Utc::now(),
        };

        self.pending.write().await.insert(run_id.clone(), pending);

        // 4. 增加全局计数
        *self.global_concurrent.write().await += 1;

        // 5. 创建执行任务并启动后台执行
        let executing_job = ExecutingJob {
            run_id: run_id.clone(),
            request: request.clone(),
            sender: response_sender.clone(),
            started_at: Utc::now(),
            seq: 0,
        };

        self.executing.write().await.insert(run_id.clone(), executing_job);

        // 6. 立即返回 accepted
        Ok(AcceptedResult {
            run_id,
            duplicate_of: None,
            cached_summary: None,
        })
    }

    /// 发送流式事件
    pub async fn emit_streaming(
        &self,
        run_id: &RunId,
        event_type: EventType,
        data: serde_json::Value,
    ) {
        let job = self.executing.read().await.get(run_id).cloned();

        if let Some(mut job) = job {
            job.seq += 1;

            let event = GatewayFrame::Event {
                run_id: run_id.clone(),
                event_type,
                seq: job.seq,
                data,
            };

            let _ = job.sender.send(event).await;

            // 更新 seq
            if let Some(j) = self.executing.write().await.get_mut(run_id) {
                j.seq = job.seq;
            }
        }
    }

    /// 发送最终结果
    pub async fn emit_final(&self, run_id: &RunId, summary: ExecutionSummary) {
        // 1. 发送给客户端
        let job = self.executing.read().await.get(run_id).cloned();

        if let Some(job) = job {
            let final_frame = GatewayFrame::Final {
                run_id: run_id.clone(),
                summary: summary.clone(),
            };

            let _ = job.sender.send(final_frame).await;
        }

        // 2. 缓存结果用于幂等
        if let Some(req) = self.executing.read().await.get(run_id) {
            if let Some(key) = &req.request.idempotency_key {
                let cached = CachedResult {
                    run_id: run_id.clone(),
                    summary: summary.clone(),
                    idempotency_key: key.clone(),
                    cached_at: Utc::now(),
                };

                self.completed.write().await.insert(key.clone(), cached);
            }
        }

        // 3. 清理
        self.executing.write().await.remove(run_id);
        self.pending.write().await.remove(run_id);

        // 4. 减少全局计数
        *self.global_concurrent.write().await -= 1;
    }

    /// 获取执行中的任务
    pub async fn get_executing(&self, run_id: &RunId) -> Option<ExecutingJob> {
        self.executing.read().await.get(run_id).cloned()
    }

    /// 获取已完成的任务
    pub async fn get_completed(&self, run_id: &RunId) -> Option<ExecutionSummary> {
        let completed = self.completed.read().await;

        for cached in completed.values() {
            if &cached.run_id == run_id {
                return Some(cached.summary.clone());
            }
        }

        None
    }

    /// 获取所有正在执行的 runId
    pub async fn get_executing_run_ids(&self) -> Vec<RunId> {
        self.executing
            .read()
            .await
            .keys()
            .cloned()
            .collect()
    }

    /// 获取全局并发数
    pub async fn get_global_concurrent(&self) -> usize {
        *self.global_concurrent.read().await
    }

    /// 清理超时的缓存 (TTL 24小时)
    pub async fn cleanup(&self) {
        let cutoff = Utc::now() - Duration::hours(24);
        let mut completed = self.completed.write().await;

        completed.retain(|_, v| v.cached_at > cutoff);
    }

    /// 检查是否有运行中的任务
    pub async fn has_active_runs(&self) -> bool {
        !self.executing.read().await.is_empty()
    }

    // ========== 私有方法 ==========

    async fn get_cached(&self, key: &str) -> Option<CachedResult> {
        self.completed.read().await.get(key).cloned()
    }
}

impl Default for TwoPhaseManager {
    fn default() -> Self {
        Self::new(10)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    fn create_test_request() -> JobRequest {
        JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test" }),
            idempotency_key: Some("test_key_123".to_string()),
            session_id: "session_123".to_string(),
            max_concurrent: 1,
        }
    }

    #[tokio::test]
    async fn test_two_phase_manager_new() {
        let manager = TwoPhaseManager::new(5);
        assert_eq!(manager.max_global_concurrent, 5);
    }

    #[tokio::test]
    async fn test_accept_returns_run_id() {
        let manager = TwoPhaseManager::new(10);
        let (tx, _rx) = mpsc::channel(10);
        
        let request = create_test_request();
        let result = manager.accept(request, tx).await.unwrap();
        
        assert!(result.run_id.as_str().starts_with("run_"));
        assert!(result.duplicate_of.is_none());
        assert!(result.cached_summary.is_none());
    }

    #[tokio::test]
    async fn test_accept_with_idempotency_cached() {
        let manager = TwoPhaseManager::new(10);
        
        // 先创建一个带 idempotency_key 的请求
        let request = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test" }),
            idempotency_key: Some("unique_key_123".to_string()),
            session_id: "session_123".to_string(),
            max_concurrent: 1,
        };
        
        let (tx1, _rx1) = mpsc::channel(10);
        let result1 = manager.accept(request.clone(), tx1).await.unwrap();
        
        // 第二次请求用同样的 idempotency_key
        let (tx2, _rx2) = mpsc::channel(10);
        let result2 = manager.accept(request, tx2).await.unwrap();
        
        // 第二次请求应该返回缓存结果
        assert!(result2.duplicate_of.is_some());
    }

    #[tokio::test]
    async fn test_emit_streaming() {
        let manager = TwoPhaseManager::new(10);
        let (tx, mut rx) = mpsc::channel(10);
        
        let request = create_test_request();
        let result = manager.accept(request, tx).await.unwrap();
        
        let run_id = result.run_id;
        manager.emit_streaming(&run_id, EventType::Streaming, serde_json::json!("Hello")).await;
        
        // 验证收到了事件
        if let Some(frame) = rx.recv().await {
            match frame {
                GatewayFrame::Event { run_id: r, event_type, seq, data } => {
                    assert_eq!(r, run_id);
                    assert_eq!(event_type, EventType::Streaming);
                    assert_eq!(seq, 1);
                    assert_eq!(data, "Hello");
                }
                _ => panic!("Expected Event frame"),
            }
        } else {
            panic!("No event received");
        }
    }

    #[tokio::test]
    async fn test_emit_final() {
        let manager = TwoPhaseManager::new(10);
        let (tx, mut rx) = mpsc::channel(10);
        
        let request = create_test_request();
        let result = manager.accept(request, tx).await.unwrap();
        
        let run_id = result.run_id.clone();
        let summary = ExecutionSummary {
            run_id: run_id.clone(),
            status: ExecutionStatus::Completed,
            output: Some("Test output".to_string()),
            tokens_used: Some(100),
            tool_calls: vec![],
            duration_ms: 500,
            error: None,
            completed_at: Utc::now(),
        };
        
        manager.emit_final(&run_id, summary).await;
        
        // 验证收到了最终结果
        if let Some(frame) = rx.recv().await {
            match frame {
                GatewayFrame::Final { run_id: r, summary } => {
                    assert_eq!(r, run_id);
                    assert_eq!(summary.status, ExecutionStatus::Completed);
                }
                _ => panic!("Expected Final frame"),
            }
        } else {
            panic!("No final received");
        }
    }

    #[tokio::test]
    async fn test_global_concurrent_limit() {
        let manager = TwoPhaseManager::new(1);
        
        let (tx1, _rx1) = mpsc::channel(10);
        let request1 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test1" }),
            idempotency_key: Some("key1".to_string()),
            session_id: "session_1".to_string(),
            max_concurrent: 1,
        };
        
        let _ = manager.accept(request1, tx1).await.unwrap();
        
        // 尝试第二个请求应该被限流
        let (tx2, _rx2) = mpsc::channel(10);
        let request2 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test2" }),
            idempotency_key: Some("key2".to_string()),
            session_id: "session_2".to_string(),
            max_concurrent: 1,
        };
        
        let result = manager.accept(request2, tx2).await;
        assert!(matches!(result, Err(AcceptError::RateLimited { .. })));
    }

    #[tokio::test]
    async fn test_get_executing_run_ids() {
        let manager = TwoPhaseManager::new(10);
        
        let (tx1, _rx1) = mpsc::channel(10);
        let (tx2, _rx2) = mpsc::channel(10);
        
        let request1 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test1" }),
            idempotency_key: Some("key_1".to_string()),
            session_id: "session_1".to_string(),
            max_concurrent: 1,
        };
        
        let request2 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test2" }),
            idempotency_key: Some("key_2".to_string()),
            session_id: "session_2".to_string(),
            max_concurrent: 1,
        };
        
        let result1 = manager.accept(request1, tx1).await.unwrap();
        let result2 = manager.accept(request2, tx2).await.unwrap();
        
        let run_ids = manager.get_executing_run_ids().await;
        assert_eq!(run_ids.len(), 2);
        assert!(run_ids.contains(&result1.run_id));
        assert!(run_ids.contains(&result2.run_id));
    }

    #[tokio::test]
    async fn test_get_global_concurrent() {
        let manager = TwoPhaseManager::new(10);
        
        let (tx1, _rx1) = mpsc::channel(10);
        let (tx2, _rx2) = mpsc::channel(10);
        
        let request1 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test1" }),
            idempotency_key: Some("key_abc".to_string()),
            session_id: "session_1".to_string(),
            max_concurrent: 1,
        };
        
        let request2 = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test2" }),
            idempotency_key: Some("key_def".to_string()),
            session_id: "session_2".to_string(),
            max_concurrent: 1,
        };
        
        let _ = manager.accept(request1, tx1).await.unwrap();
        let _ = manager.accept(request2, tx2).await.unwrap();
        
        assert_eq!(manager.get_global_concurrent().await, 2);
    }

    #[tokio::test]
    async fn test_has_active_runs() {
        let manager = TwoPhaseManager::new(10);
        
        assert!(!manager.has_active_runs().await);
        
        let (tx, _rx) = mpsc::channel(10);
        let request = JobRequest {
            method: "agent".to_string(),
            params: serde_json::json!({ "message": "test" }),
            idempotency_key: Some("key_xyz".to_string()),
            session_id: "session_1".to_string(),
            max_concurrent: 1,
        };
        
        let _ = manager.accept(request, tx).await.unwrap();
        
        assert!(manager.has_active_runs().await);
    }
}
