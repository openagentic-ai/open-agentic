//! 幂等键与去重机制实现

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use chrono::{Duration as ChronoDuration, Utc};
use tokio::sync::{mpsc, RwLock};

use crate::gateway::protocol::{ExecutionSummary, GatewayFrame, RunId};
use crate::gateway::two_phase::CachedResult;

pub struct DeduplicationLayer {
    completed_cache: Arc<RwLock<HashMap<String, CachedResult>>>,
    inflight: Arc<RwLock<HashMap<String, InflightRequest>>>,
}

struct InflightRequest {
    primary_sender: mpsc::Sender<GatewayFrame>,
    subscribers: Vec<mpsc::Sender<GatewayFrame>>,
    created_at: chrono::DateTime<Utc>,
}

impl DeduplicationLayer {
    pub fn new() -> Self {
        Self {
            completed_cache: Arc::new(RwLock::new(HashMap::new())),
            inflight: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// 检查并处理请求
    ///
    /// 返回:
    /// - Some(CachedResult): 如果已缓存完成，直接返回缓存结果
    /// - None: 需要执行新请求，会注册到 inflight
    pub async fn check_or_register(
        &self,
        idempotency_key: &str,
        sender: mpsc::Sender<GatewayFrame>,
    ) -> Option<CachedResult> {
        // 1. 先查已完成缓存
        let cached = self
            .completed_cache
            .read()
            .await
            .get(idempotency_key)
            .cloned();
        if let Some(cached) = cached {
            tracing::debug!("Dedupe hit (completed): {}", idempotency_key);
            return Some(cached);
        }

        // 2. 查飞行中
        let mut inflight = self.inflight.write().await;

        if let Some(existing) = inflight.get_mut(idempotency_key) {
            tracing::debug!("Dedupe hit (inflight): {}", idempotency_key);
            existing.subscribers.push(sender);
            return None;
        }

        // 3. 新请求，注册到飞行中
        inflight.insert(
            idempotency_key.to_string(),
            InflightRequest {
                primary_sender: sender.clone(),
                subscribers: Vec::new(),
                created_at: Utc::now(),
            },
        );

        None
    }

    /// 标记请求已完成
    pub async fn mark_completed(&self, idempotency_key: &str, result: CachedResult) {
        // 1. 写入缓存
        self.completed_cache
            .write()
            .await
            .insert(idempotency_key.to_string(), result.clone());

        // 2. 从飞行中移除
        let subscribers = {
            let mut inflight = self.inflight.write().await;

            if let Some(entry) = inflight.remove(idempotency_key) {
                entry.subscribers
            } else {
                Vec::new()
            }
        };

        // 3. 广播给所有订阅者
        let final_frame = GatewayFrame::Final {
            run_id: result.run_id.clone(),
            summary: result.summary.clone(),
        };

        for subscriber in subscribers {
            let _ = subscriber.send(final_frame.clone()).await;
        }
    }

    /// 从飞行中移除 (请求失败或取消)
    pub async fn remove_inflight(&self, idempotency_key: &str) {
        self.inflight.write().await.remove(idempotency_key);
    }

    /// 清理超时飞行中请求 (超时: 5分钟)
    pub async fn cleanup_inflight(&self) {
        let cutoff = Utc::now() - ChronoDuration::minutes(5);

        let mut inflight = self.inflight.write().await;
        inflight.retain(|_, v| v.created_at > cutoff);
    }

    /// 清理过期缓存 (TTL: 24小时)
    pub async fn cleanup_cache(&self) {
        let cutoff = Utc::now() - ChronoDuration::hours(24);

        let mut cache = self.completed_cache.write().await;
        cache.retain(|_, v| v.cached_at > cutoff);
    }

    /// 获取缓存结果
    pub async fn get_cached(&self, idempotency_key: &str) -> Option<CachedResult> {
        self.completed_cache
            .read()
            .await
            .get(idempotency_key)
            .cloned()
    }

    /// 检查是否在飞行中
    pub async fn is_inflight(&self, idempotency_key: &str) -> bool {
        self.inflight.read().await.contains_key(idempotency_key)
    }

    /// 获取飞行中的订阅者数量
    pub async fn get_inflight_subscriber_count(&self, idempotency_key: &str) -> usize {
        self.inflight
            .read()
            .await
            .get(idempotency_key)
            .map(|r| r.subscribers.len())
            .unwrap_or(0)
    }

    /// 获取缓存数量
    pub async fn cache_size(&self) -> usize {
        self.completed_cache.read().await.len()
    }

    /// 获取飞行中数量
    pub async fn inflight_size(&self) -> usize {
        self.inflight.read().await.len()
    }
}

impl Default for DeduplicationLayer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    fn create_test_cached_result(key: &str) -> CachedResult {
        CachedResult {
            run_id: RunId::from_string(format!("run_{}", key)),
            summary: ExecutionSummary {
                run_id: RunId::from_string(format!("run_{}", key)),
                status: crate::gateway::protocol::ExecutionStatus::Completed,
                output: Some("test output".to_string()),
                tokens_used: Some(100),
                tool_calls: vec![],
                duration_ms: 500,
                error: None,
                completed_at: Utc::now(),
            },
            idempotency_key: key.to_string(),
            cached_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn test_deduplication_new() {
        let dedup = DeduplicationLayer::new();
        assert_eq!(dedup.cache_size().await, 0);
        assert_eq!(dedup.inflight_size().await, 0);
    }

    #[tokio::test]
    async fn test_check_or_register_new_key() {
        let dedup = DeduplicationLayer::new();
        let (tx, _rx) = mpsc::channel(10);

        let result = dedup.check_or_register("key1", tx).await;
        assert!(result.is_none());
        assert!(dedup.is_inflight("key1").await);
    }

    #[tokio::test]
    async fn test_check_or_register_hit_cache() {
        let dedup = DeduplicationLayer::new();
        
        // 先手动插入缓存
        let cached = create_test_cached_result("cached_key");
        dedup.completed_cache.write().await.insert(
            "cached_key".to_string(),
            cached.clone(),
        );

        let (tx, _rx) = mpsc::channel(10);
        let result = dedup.check_or_register("cached_key", tx).await;

        assert!(result.is_some());
        assert_eq!(result.unwrap().run_id.as_str(), "run_cached_key");
    }

    #[tokio::test]
    async fn test_check_or_register_hit_inflight() {
        let dedup = DeduplicationLayer::new();
        
        // 先注册一个飞行中的请求
        let (tx1, _rx1) = mpsc::channel(10);
        let _ = dedup.check_or_register("inflight_key", tx1).await;

        // 第二次注册同一个 key
        let (tx2, _rx2) = mpsc::channel(10);
        let result = dedup.check_or_register("inflight_key", tx2).await;

        assert!(result.is_none());
        // 应该有2个订阅者
        assert_eq!(dedup.get_inflight_subscriber_count("inflight_key").await, 1);
    }

    #[tokio::test]
    async fn test_mark_completed() {
        let dedup = DeduplicationLayer::new();
        
        // 注册飞行中
        let (tx, _rx) = mpsc::channel(10);
        let _ = dedup.check_or_register("key_complete", tx).await;

        // 标记完成
        let cached = create_test_cached_result("key_complete");
        dedup.mark_completed("key_complete", cached).await;

        // 验证缓存已写入
        assert!(dedup.get_cached("key_complete").await.is_some());
        // 验证已从飞行中移除
        assert!(!dedup.is_inflight("key_complete").await);
    }

    #[tokio::test]
    async fn test_remove_inflight() {
        let dedup = DeduplicationLayer::new();
        
        let (tx, _rx) = mpsc::channel(10);
        let _ = dedup.check_or_register("key_remove", tx).await;

        assert!(dedup.is_inflight("key_remove").await);

        dedup.remove_inflight("key_remove").await;

        assert!(!dedup.is_inflight("key_remove").await);
    }

    #[tokio::test]
    async fn test_cleanup_cache() {
        let dedup = DeduplicationLayer::new();

        // 插入过期缓存
        let mut old_cached = create_test_cached_result("old_key");
        old_cached.cached_at = Utc::now() - ChronoDuration::hours(25);
        
        dedup.completed_cache.write().await.insert(
            "old_key".to_string(),
            old_cached,
        );

        // 插入新缓存
        let new_cached = create_test_cached_result("new_key");
        dedup.completed_cache.write().await.insert(
            "new_key".to_string(),
            new_cached,
        );

        dedup.cleanup_cache().await;

        assert!(dedup.get_cached("old_key").await.is_none());
        assert!(dedup.get_cached("new_key").await.is_some());
    }

    #[tokio::test]
    async fn test_cleanup_inflight() {
        let dedup = DeduplicationLayer::new();

        // 插入过期飞行中
        let mut inflight = InflightRequest {
            primary_sender: mpsc::channel(10).0,
            subscribers: vec![],
            created_at: Utc::now() - ChronoDuration::minutes(10),
        };
        
        let mut dedup_inflight = dedup.inflight.write().await;
        dedup_inflight.insert("old_inflight".to_string(), inflight);

        // 插入新的飞行中
        let new_inflight = InflightRequest {
            primary_sender: mpsc::channel(10).0,
            subscribers: vec![],
            created_at: Utc::now(),
        };
        dedup_inflight.insert("new_inflight".to_string(), new_inflight);
        drop(dedup_inflight);

        dedup.cleanup_inflight().await;

        assert!(!dedup.is_inflight("old_inflight").await);
        assert!(dedup.is_inflight("new_inflight").await);
    }

    #[tokio::test]
    async fn test_multiple_subscribers_broadcast() {
        let dedup = DeduplicationLayer::new();
        
        // 注册多个订阅者
        let (tx1, mut rx1) = mpsc::channel(10);
        let (tx2, mut rx2) = mpsc::channel(10);
        
        let _ = dedup.check_or_register("broadcast_key", tx1).await;
        let _ = dedup.check_or_register("broadcast_key", tx2).await;

        // 标记完成
        let cached = create_test_cached_result("broadcast_key");
        dedup.mark_completed("broadcast_key", cached.clone()).await;

        // 两个订阅者都应该收到广播
        let frame1 = tokio::time::timeout(std::time::Duration::from_millis(100), rx1.recv()).await;
        let frame2 = tokio::time::timeout(std::time::Duration::from_millis(100), rx2.recv()).await;

        assert!(frame1.is_ok());
        assert!(frame2.is_ok());
    }

    #[tokio::test]
    async fn test_cache_size() {
        let dedup = DeduplicationLayer::new();
        
        assert_eq!(dedup.cache_size().await, 0);
        
        let cached = create_test_cached_result("size_test");
        dedup.completed_cache.write().await.insert("size_test".to_string(), cached);
        
        assert_eq!(dedup.cache_size().await, 1);
    }

    #[tokio::test]
    async fn test_inflight_size() {
        let dedup = DeduplicationLayer::new();
        
        assert_eq!(dedup.inflight_size().await, 0);
        
        let (tx, _rx) = mpsc::channel(10);
        dedup.check_or_register("size_test", tx).await;
        
        assert_eq!(dedup.inflight_size().await, 1);
    }
}
