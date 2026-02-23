//! Rate Limit Service - 速率限制服务
//!
//! 提供基于令牌桶的速率限制

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;

#[derive(Debug, Error)]
pub enum RateLimitError {
    #[error("Rate limit exceeded")]
    RateLimitExceeded,
    
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),
    
    #[error("Tool not found: {0}")]
    ToolNotFound(String),
    
    #[error("Storage error: {0}")]
    StorageError(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConfig {
    pub requests_per_minute: u32,
    pub requests_per_hour: Option<u32>,
    pub burst_size: Option<u32>,
}

impl RateLimitConfig {
    pub fn per_minute(rpm: u32) -> Self {
        Self {
            requests_per_minute: rpm,
            requests_per_hour: None,
            burst_size: Some(rpm),
        }
    }
    
    pub fn per_hour(rph: u32) -> Self {
        Self {
            requests_per_minute: 0,
            requests_per_hour: Some(rph),
            burst_size: Some(rph / 60),
        }
    }
    
    pub fn with_burst(mut self, burst: u32) -> Self {
        self.burst_size = Some(burst);
        self
    }
}

#[derive(Debug, Clone)]
pub struct TokenBucket {
    pub tokens: f64,
    pub last_refill: DateTime<Utc>,
    pub capacity: f64,
    pub refill_rate: f64,
}

impl TokenBucket {
    pub fn new(capacity: f64, refill_rate: f64) -> Self {
        Self {
            tokens: capacity,
            last_refill: Utc::now(),
            capacity,
            refill_rate,
        }
    }
    
    pub fn try_consume(&mut self, tokens: f64) -> bool {
        self.refill();
        if self.tokens >= tokens {
            self.tokens -= tokens;
            true
        } else {
            false
        }
    }
    
    fn refill(&mut self) {
        let now = Utc::now();
        let elapsed = (now - self.last_refill).num_milliseconds() as f64 / 1000.0;
        self.tokens = (self.tokens + elapsed * self.refill_rate).min(self.capacity);
        self.last_refill = now;
    }
}

#[async_trait]
pub trait RateLimiter: Send + Sync {
    async fn check_limit(&self, key: &str) -> Result<(), RateLimitError>;
    
    async fn configure_tool_limits(&self, tool_id: &str, config: RateLimitConfig) -> Result<(), RateLimitError>;
    
    async fn get_remaining(&self, key: &str) -> Result<u64, RateLimitError>;
    
    async fn get_reset_time(&self, key: &str) -> Result<DateTime<Utc>, RateLimitError>;
    
    async fn reset(&self, key: &str) -> Result<(), RateLimitError>;
    
    async fn list_configured(&self) -> Result<Vec<String>, RateLimitError>;
}

pub struct MemoryRateLimiter {
    buckets: Arc<RwLock<HashMap<String, TokenBucket>>>,
    configs: Arc<RwLock<HashMap<String, RateLimitConfig>>>,
}

impl Default for MemoryRateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

impl MemoryRateLimiter {
    pub fn new() -> Self {
        Self {
            buckets: Arc::new(RwLock::new(HashMap::new())),
            configs: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub fn with_config(configs: HashMap<String, RateLimitConfig>) -> Self {
        let mut buckets = HashMap::new();
        for (key, config) in &configs {
            let capacity = config.burst_size.unwrap_or(config.requests_per_minute) as f64;
            let refill_rate = config.requests_per_minute as f64 / 60.0;
            buckets.insert(key.clone(), TokenBucket::new(capacity, refill_rate));
        }
        
        Self {
            buckets: Arc::new(RwLock::new(buckets)),
            configs: Arc::new(RwLock::new(configs)),
        }
    }
    
    #[allow(dead_code)]
    async fn get_or_create_bucket(&self, key: &str) -> TokenBucket {
        let mut buckets = self.buckets.write().await;
        if let Some(bucket) = buckets.get(key) {
            bucket.clone()
        } else {
            let bucket = TokenBucket::new(60.0, 1.0);
            buckets.insert(key.to_string(), bucket.clone());
            bucket
        }
    }
}

#[async_trait]
impl RateLimiter for MemoryRateLimiter {
    async fn check_limit(&self, key: &str) -> Result<(), RateLimitError> {
        let mut buckets = self.buckets.write().await;
        
        let bucket = if let Some(bucket) = buckets.get_mut(key) {
            bucket
        } else {
            let bucket = TokenBucket::new(60.0, 1.0);
            buckets.insert(key.to_string(), bucket);
            buckets.get_mut(key).unwrap()
        };
        
        if bucket.try_consume(1.0) {
            Ok(())
        } else {
            Err(RateLimitError::RateLimitExceeded)
        }
    }
    
    async fn configure_tool_limits(&self, tool_id: &str, config: RateLimitConfig) -> Result<(), RateLimitError> {
        if config.requests_per_minute == 0 && config.requests_per_hour.is_none() {
            return Err(RateLimitError::InvalidConfig("At least one rate limit must be set".to_string()));
        }
        
        let capacity = config.burst_size.unwrap_or(config.requests_per_minute.max(1)) as f64;
        let refill_rate = if config.requests_per_minute > 0 {
            config.requests_per_minute as f64 / 60.0
        } else {
            config.requests_per_hour.unwrap() as f64 / 3600.0
        };
        
        let mut buckets = self.buckets.write().await;
        buckets.insert(tool_id.to_string(), TokenBucket::new(capacity, refill_rate));
        
        let mut configs = self.configs.write().await;
        configs.insert(tool_id.to_string(), config);
        
        Ok(())
    }
    
    async fn get_remaining(&self, key: &str) -> Result<u64, RateLimitError> {
        let buckets = self.buckets.read().await;
        if let Some(bucket) = buckets.get(key) {
            Ok(bucket.tokens as u64)
        } else {
            Ok(60)
        }
    }
    
    async fn get_reset_time(&self, key: &str) -> Result<DateTime<Utc>, RateLimitError> {
        let buckets = self.buckets.read().await;
        if let Some(bucket) = buckets.get(key) {
            let tokens_needed = (bucket.capacity - bucket.tokens).max(0.0);
            let seconds = tokens_needed / bucket.refill_rate;
            Ok(bucket.last_refill + chrono::Duration::seconds(seconds as i64))
        } else {
            Ok(Utc::now())
        }
    }
    
    async fn reset(&self, key: &str) -> Result<(), RateLimitError> {
        let mut buckets = self.buckets.write().await;
        buckets.remove(key);
        Ok(())
    }
    
    async fn list_configured(&self) -> Result<Vec<String>, RateLimitError> {
        let configs = self.configs.read().await;
        Ok(configs.keys().cloned().collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_token_bucket_creation() {
        let bucket = TokenBucket::new(10.0, 1.0);
        assert_eq!(bucket.capacity, 10.0);
        assert_eq!(bucket.refill_rate, 1.0);
    }
    
    #[test]
    fn test_token_bucket_consume() {
        let mut bucket = TokenBucket::new(5.0, 1.0);
        assert!(bucket.try_consume(1.0));
        assert!(bucket.try_consume(1.0));
        assert!(bucket.try_consume(1.0));
    }
    
    #[test]
    fn test_token_bucket_exhausted() {
        let mut bucket = TokenBucket::new(2.0, 1.0);
        assert!(bucket.try_consume(1.0));
        assert!(bucket.try_consume(1.0));
        assert!(!bucket.try_consume(1.0));
    }
    
    #[test]
    fn test_rate_limit_config_per_minute() {
        let config = RateLimitConfig::per_minute(60);
        assert_eq!(config.requests_per_minute, 60);
    }
    
    #[test]
    fn test_rate_limit_config_with_burst() {
        let config = RateLimitConfig::per_minute(60).with_burst(100);
        assert_eq!(config.burst_size, Some(100));
    }
    
    #[tokio::test]
    async fn test_check_limit_allows() {
        let limiter = MemoryRateLimiter::new();
        limiter.configure_tool_limits("test-tool", RateLimitConfig::per_minute(10))
            .await
            .unwrap();
        
        let result = limiter.check_limit("test-tool").await;
        assert!(result.is_ok());
    }
    
    #[tokio::test]
    async fn test_check_limit_exceeds() {
        let limiter = MemoryRateLimiter::new();
        limiter.configure_tool_limits("test-tool", RateLimitConfig::per_minute(1))
            .await
            .unwrap();
        
        limiter.check_limit("test-tool").await.unwrap();
        let result = limiter.check_limit("test-tool").await;
        
        assert!(matches!(result, Err(RateLimitError::RateLimitExceeded)));
    }
    
    #[tokio::test]
    async fn test_get_remaining() {
        let limiter = MemoryRateLimiter::new();
        limiter.configure_tool_limits("test-tool", RateLimitConfig::per_minute(10))
            .await
            .unwrap();
        
        let remaining = limiter.get_remaining("test-tool").await.unwrap();
        assert!(remaining >= 0 && remaining <= 10);
    }
    
    #[tokio::test]
    async fn test_reset() {
        let limiter = MemoryRateLimiter::new();
        limiter.configure_tool_limits("test-tool", RateLimitConfig::per_minute(1))
            .await
            .unwrap();
        
        limiter.check_limit("test-tool").await.unwrap();
        limiter.reset("test-tool").await.unwrap();
        
        let result = limiter.check_limit("test-tool").await;
        assert!(result.is_ok());
    }
    
    #[tokio::test]
    async fn test_list_configured() {
        let limiter = MemoryRateLimiter::new();
        limiter.configure_tool_limits("tool1", RateLimitConfig::per_minute(10))
            .await
            .unwrap();
        limiter.configure_tool_limits("tool2", RateLimitConfig::per_minute(20))
            .await
            .unwrap();
        
        let tools = limiter.list_configured().await.unwrap();
        assert_eq!(tools.len(), 2);
    }
}
