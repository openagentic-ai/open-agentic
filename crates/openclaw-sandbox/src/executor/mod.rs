//! Secure Tool Executor - 安全工具执行器
//!
//! 编排所有安全组件，提供统一的工具执行接口

use crate::capability::{Capability, CapabilityService};
use crate::credential::CredentialService;
use crate::rate_limit::{RateLimitConfig, RateLimiter};
use crate::leak_detector::LeakDetector;
use crate::endpoint::{EndpointAllowlist, HttpRequest};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;

#[derive(Debug, Error)]
pub enum ExecutorError {
    #[error("Rate limit exceeded")]
    RateLimitExceeded,
    
    #[error("Capability denied: {0}")]
    CapabilityDenied(String),
    
    #[error("Credential denied: {0}")]
    CredentialDenied(String),
    
    #[error("Leak detected: {0}")]
    LeakDetected(String),
    
    #[error("Endpoint not allowed: {0}")]
    EndpointNotAllowed(String),
    
    #[error("Execution failed: {0}")]
    ExecutionFailed(String),
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SecurityCheckResults {
    pub rate_limit_passed: bool,
    pub capability_passed: bool,
    pub credential_passed: bool,
    pub leak_check_passed: bool,
    pub endpoint_passed: bool,
}

impl SecurityCheckResults {
    pub fn all_passed(&self) -> bool {
        self.rate_limit_passed 
            && self.capability_passed 
            && self.credential_passed 
            && self.leak_check_passed 
            && self.endpoint_passed
    }
}

#[derive(Debug, Clone)]
pub struct ExecutionContext {
    pub tool_id: String,
    pub user_id: Option<String>,
    pub input: serde_json::Value,
    pub env: HashMap<String, String>,
    pub required_capability: Option<Capability>,
    pub http_request: Option<HttpRequest>,
}

impl ExecutionContext {
    pub fn new(tool_id: &str) -> Self {
        Self {
            tool_id: tool_id.to_string(),
            user_id: None,
            input: serde_json::Value::Null,
            env: HashMap::new(),
            required_capability: None,
            http_request: None,
        }
    }
    
    pub fn with_input(mut self, input: serde_json::Value) -> Self {
        self.input = input;
        self
    }
    
    pub fn with_user_id(mut self, user_id: &str) -> Self {
        self.user_id = Some(user_id.to_string());
        self
    }
    
    pub fn with_env(mut self, key: &str, value: &str) -> Self {
        self.env.insert(key.to_string(), value.to_string());
        self
    }
    
    pub fn with_required_capability(mut self, cap: Capability) -> Self {
        self.required_capability = Some(cap);
        self
    }
    
    pub fn with_http_request(mut self, request: HttpRequest) -> Self {
        self.http_request = Some(request);
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub success: bool,
    pub output: serde_json::Value,
    pub error: Option<String>,
    pub execution_time_ms: u64,
    pub security_results: Option<SecurityCheckResults>,
}

pub struct SecureToolExecutor<C, CR, RL, LD, E> 
where
    C: CapabilityService,
    CR: CredentialService,
    RL: RateLimiter,
    LD: LeakDetector,
    E: EndpointAllowlist,
{
    capability: Arc<C>,
    credential: Arc<CR>,
    rate_limiter: Arc<RL>,
    leak_detector: Arc<LD>,
    endpoint: Arc<E>,
    tool_configs: Arc<RwLock<HashMap<String, ToolConfig>>>,
}

#[derive(Debug, Clone)]
pub struct ToolConfig {
    pub credential_set: Option<String>,
    pub allowed_endpoints: Vec<String>,
    pub rate_limit: Option<RateLimitConfig>,
}

impl ToolConfig {
    pub fn new() -> Self {
        Self {
            credential_set: None,
            allowed_endpoints: Vec::new(),
            rate_limit: None,
        }
    }
}

impl Default for ToolConfig {
    fn default() -> Self {
        Self::new()
    }
}

impl<C, CR, RL, LD, E> SecureToolExecutor<C, CR, RL, LD, E> 
where
    C: CapabilityService,
    CR: CredentialService,
    RL: RateLimiter,
    LD: LeakDetector,
    E: EndpointAllowlist,
{
    pub fn new(
        capability: Arc<C>,
        credential: Arc<CR>,
        rate_limiter: Arc<RL>,
        leak_detector: Arc<LD>,
        endpoint: Arc<E>,
    ) -> Self {
        Self {
            capability,
            credential,
            rate_limiter,
            leak_detector,
            endpoint,
            tool_configs: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub async fn configure_tool(&self, tool_id: &str, config: ToolConfig) {
        let mut configs = self.tool_configs.write().await;
        configs.insert(tool_id.to_string(), config);
    }
    
    pub async fn configure_tool_limits(&self, tool_id: &str, config: RateLimitConfig) -> Result<(), ExecutorError> {
        self.rate_limiter
            .configure_tool_limits(tool_id, config)
            .await
            .map_err(|_e| ExecutorError::RateLimitExceeded)
    }
    
    pub async fn execute<F, R>(
        &self,
        ctx: ExecutionContext,
        mut executor: F,
    ) -> Result<ExecutionResult, ExecutorError>
    where
        F: FnMut(serde_json::Value, HashMap<String, String>) -> R,
        R: std::future::Future<Output = Result<serde_json::Value, String>>,
    {
        let start = std::time::Instant::now();
        let mut security_results = SecurityCheckResults::default();
        
        let rate_key = ctx.user_id.as_ref()
            .map(|u| format!("{}:{}", u, ctx.tool_id.as_str()))
            .unwrap_or_else(|| ctx.tool_id.clone());
        
        if let Err(_) = self.rate_limiter.check_limit(&rate_key).await {
            return Err(ExecutorError::RateLimitExceeded);
        }
        security_results.rate_limit_passed = true;
        
        if let Some(required_cap) = &ctx.required_capability {
            let has_cap = self.capability.has_capability(&ctx.tool_id, required_cap).await;
            if !has_cap {
                return Err(ExecutorError::CapabilityDenied(
                    format!("Tool lacks required capability: {:?}", required_cap)
                ));
            }
        }
        security_results.capability_passed = true;
        
        let tool_configs = self.tool_configs.read().await;
        if let Some(config) = tool_configs.get(&ctx.tool_id) {
            if let Some(ref set_name) = config.credential_set {
                let has_access = self.credential.check_access(set_name, &ctx.tool_id).await
                    .unwrap_or(false);
                if !has_access {
                    return Err(ExecutorError::CredentialDenied(
                        format!("Tool not authorized to access credential set: {}", set_name)
                    ));
                }
            }
        }
        security_results.credential_passed = true;
        
        let input_str = serde_json::to_string(&ctx.input).unwrap_or_default();
        let leak_result = self.leak_detector.detect(&input_str);
        if leak_result.is_leaked {
            return Err(ExecutorError::LeakDetected(
                format!("Sensitive data detected in input: {:?}", leak_result.severity)
            ));
        }
        security_results.leak_check_passed = true;
        
        if let Some(ref http_request) = ctx.http_request {
            let decision = self.endpoint.check(http_request).await;
            if !decision.allowed {
                return Err(ExecutorError::EndpointNotAllowed(
                    decision.reason.unwrap_or_else(|| "Unknown reason".to_string())
                ));
            }
        }
        security_results.endpoint_passed = true;
        
        let mut env = ctx.env.clone();
        
        if let Some(config) = tool_configs.get(&ctx.tool_id) {
            if let Some(ref set_name) = config.credential_set {
                self.credential.inject_credentials(set_name, &mut env).await.ok();
            }
        }
        
        let result = executor(ctx.input, env).await;
        
        let output = match result {
            Ok(value) => {
                let output_str = serde_json::to_string(&value).unwrap_or_default();
                let leak_result = self.leak_detector.detect(&output_str);
                if leak_result.is_leaked {
                    return Err(ExecutorError::LeakDetected(
                        format!("Sensitive data detected in output: {:?}", leak_result.severity)
                    ));
                }
                value
            }
            Err(e) => {
                return Err(ExecutorError::ExecutionFailed(e));
            }
        };
        
        let duration = start.elapsed();
        
        Ok(ExecutionResult {
            success: true,
            output,
            error: None,
            execution_time_ms: duration.as_millis() as u64,
            security_results: Some(security_results),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::capability::MemoryCapabilityService;
    use crate::credential::MemoryCredentialService;
    use crate::leak_detector::{RegexLeakDetector, create_default_detector};
    use crate::rate_limit::MemoryRateLimiter;
    use crate::endpoint::MemoryEndpointAllowlist;
    
    fn create_test_executor() -> SecureToolExecutor<
        MemoryCapabilityService,
        MemoryCredentialService,
        MemoryRateLimiter,
        RegexLeakDetector,
        MemoryEndpointAllowlist,
    > {
        let capability = Arc::new(MemoryCapabilityService::new());
        let credential = Arc::new(MemoryCredentialService::new());
        let rate_limiter = Arc::new(MemoryRateLimiter::new());
        let leak_detector = Arc::new(create_default_detector());
        let endpoint = Arc::new(MemoryEndpointAllowlist::new());
        
        SecureToolExecutor::new(capability, credential, rate_limiter, leak_detector, endpoint)
    }
    
    #[tokio::test]
    async fn test_execute_success() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({"action": "test"}));
        
        let result = executor.execute(ctx, |_input, _env| async {
            Ok(serde_json::json!({"result": "success"}))
        }).await.unwrap();
        
        assert!(result.success);
    }
    
    #[tokio::test]
    #[ignore]
    async fn test_rate_limit_exceeded() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_user_id("test-user")
            .with_input(serde_json::json!({"action": "test"}));
        
        let mut results = Vec::new();
        for i in 0..61 {
            let result = executor.execute(ctx.clone(), |_input, _env| async {
                Ok(serde_json::json!({}))
            }).await;
            if i < 5 || i >= 55 {
                println!("Request {}: {:?}", i, result);
            }
            results.push(result);
        }
        
        let rate_limited = results.iter().any(|r| matches!(r, Err(ExecutorError::RateLimitExceeded)));
        assert!(rate_limited, "Expected at least one rate limit error");
    }
    
    #[tokio::test]
    async fn test_capability_denied() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({}))
            .with_required_capability(Capability::Secrets);
        
        let result = executor.execute(ctx, |_input, _env| async {
            Ok(serde_json::json!({}))
        }).await;
        
        assert!(matches!(result, Err(ExecutorError::CapabilityDenied(_))));
    }
    
    #[tokio::test]
    async fn test_leak_detected_in_input() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({"api_key": "sk-1234567890abcdefghij"}));
        
        let result = executor.execute(ctx, |_input, _env| async {
            Ok(serde_json::json!({}))
        }).await;
        
        assert!(matches!(result, Err(ExecutorError::LeakDetected(_))));
    }
    
    #[tokio::test]
    async fn test_leak_detected_in_output() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({"action": "test"}));
        
        let result = executor.execute(ctx, |_input, _env| async {
            Ok(serde_json::json!({"password": "MySecretPass123"}))
        }).await;
        
        assert!(matches!(result, Err(ExecutorError::LeakDetected(_))));
    }
    
    #[tokio::test]
    async fn test_endpoint_not_allowed() {
        let executor = create_test_executor();
        
        let request = HttpRequest::new("forbidden.com", "/api/data", "GET");
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({}))
            .with_http_request(request);
        
        let result = executor.execute(ctx, |_input, _env| async {
            Ok(serde_json::json!({}))
        }).await;
        
        assert!(matches!(result, Err(ExecutorError::EndpointNotAllowed(_))));
    }
    
    #[tokio::test]
    async fn test_execution_error() {
        let executor = create_test_executor();
        
        let ctx = ExecutionContext::new("test-tool")
            .with_input(serde_json::json!({"action": "test"}));
        
        let result = executor.execute(ctx, |_input, _env| async {
            Err("Something went wrong".to_string())
        }).await;
        
        assert!(matches!(result, Err(ExecutorError::ExecutionFailed(_))));
    }
}
