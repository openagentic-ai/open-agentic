use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};

use super::message_bus::AgentMessage;
use super::metrics::CollaborationMetrics;

pub struct MessageRouter {
    metrics: Arc<CollaborationMetrics>,
    routing_rules: Arc<RwLock<HashMap<String, Vec<RouteRule>>>>,
    fallback_agents: Arc<RwLock<HashMap<String, String>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteRule {
    pub from_agent: String,
    pub to_agent: String,
    pub priority: u32,
    pub conditions: Vec<RouteCondition>,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteCondition {
    pub field: String,
    pub operator: RouteOperator,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum RouteOperator {
    #[serde(rename = "equals")]
    Equals,
    #[serde(rename = "not_equals")]
    NotEquals,
    #[serde(rename = "contains")]
    Contains,
    #[serde(rename = "starts_with")]
    StartsWith,
    #[serde(rename = "ends_with")]
    EndsWith,
    #[serde(rename = "regex")]
    Regex,
    #[serde(rename = "greater_than")]
    GreaterThan,
    #[serde(rename = "less_than")]
    LessThan,
}

impl Default for RouteOperator {
    fn default() -> Self {
        RouteOperator::Equals
    }
}

impl MessageRouter {
    pub fn new(metrics: Arc<CollaborationMetrics>) -> Self {
        Self {
            metrics,
            routing_rules: Arc::new(RwLock::new(HashMap::new())),
            fallback_agents: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn add_route(&self, rule: RouteRule) -> Result<(), String> {
        let mut rules = self.routing_rules.write().await;
        rules
            .entry(rule.from_agent.clone())
            .or_default()
            .push(rule);
        Ok(())
    }

    pub async fn remove_route(&self, from_agent: &str, to_agent: &str) -> Result<(), String> {
        let mut rules = self.routing_rules.write().await;
        if let Some(agent_rules) = rules.get_mut(from_agent) {
            agent_rules.retain(|r| r.to_agent != to_agent);
        }
        Ok(())
    }

    pub async fn set_fallback_agent(&self, agent_id: &str, fallback: String) -> Result<(), String> {
        let mut fallbacks = self.fallback_agents.write().await;
        fallbacks.insert(agent_id.to_string(), fallback);
        Ok(())
    }

    pub async fn route(&self, message: &AgentMessage) -> Option<String> {
        self.metrics.record_message().await;

        let rules = self.routing_rules.read().await;
        
        if let Some(agent_rules) = rules.get(&message.from_agent) {
            for rule in agent_rules.iter().filter(|r| r.enabled) {
                if self.match_conditions(&rule.conditions, message).await {
                    self.metrics.record_delegation_start(super::metrics::DelegationState {
                        task_id: message.id.clone(),
                        from_agent: message.from_agent.clone(),
                        to_agent: rule.to_agent.clone(),
                        status: super::metrics::MetricDelegationStatus::Pending,
                        started_at: message.timestamp,
                        completed_at: None,
                    }).await;
                    return Some(rule.to_agent.clone());
                }
            }
        }

        let fallback = self.fallback_agents.read().await;
        fallback.get(&message.from_agent).cloned()
    }

    pub async fn route_delegation(&self, from_agent: &str, task_input: &str) -> Vec<String> {
        let rules = self.routing_rules.read().await;
        
        let mut matched_agents = Vec::new();
        
        if let Some(agent_rules) = rules.get(from_agent) {
            for rule in agent_rules.iter().filter(|r| r.enabled) {
                if self.match_task_conditions(&rule.conditions, task_input).await {
                    matched_agents.push(rule.to_agent.clone());
                }
            }
        }

        matched_agents
    }

    pub async fn list_routes(&self, agent_id: &str) -> Vec<RouteRule> {
        let rules = self.routing_rules.read().await;
        rules.get(agent_id).cloned().unwrap_or_default()
    }

    pub async fn list_all_routes(&self) -> HashMap<String, Vec<RouteRule>> {
        let rules = self.routing_rules.read().await;
        rules.clone()
    }

    pub async fn clear_routes(&self, agent_id: &str) {
        let mut rules = self.routing_rules.write().await;
        rules.remove(agent_id);
    }

    async fn match_conditions(&self, conditions: &[RouteCondition], message: &AgentMessage) -> bool {
        for condition in conditions {
            let field_value = self.get_field_value(&condition.field, message);
            if !self.evaluate_condition(&condition.operator, &field_value, &condition.value) {
                return false;
            }
        }
        true
    }

    async fn match_task_conditions(&self, conditions: &[RouteCondition], task_input: &str) -> bool {
        for condition in conditions {
            let field_value = task_input.to_string();
            if !self.evaluate_condition(&condition.operator, &field_value, &condition.value) {
                return false;
            }
        }
        true
    }

    fn get_field_value(&self, field: &str, message: &AgentMessage) -> String {
        match field {
            "message_type" => format!("{:?}", message.message_type),
            "content" => message.content.clone(),
            "from_agent" => message.from_agent.clone(),
            "to_agent" => message.to_agent.clone(),
            _ => message.context.get(field).cloned().unwrap_or_default(),
        }
    }

    fn evaluate_condition(&self, operator: &RouteOperator, actual: &str, expected: &str) -> bool {
        match operator {
            RouteOperator::Equals => actual == expected,
            RouteOperator::NotEquals => actual != expected,
            RouteOperator::Contains => actual.contains(expected),
            RouteOperator::StartsWith => actual.starts_with(expected),
            RouteOperator::EndsWith => actual.ends_with(expected),
            RouteOperator::Regex => {
                regex::Regex::new(expected)
                    .map(|re| re.is_match(actual))
                    .unwrap_or(false)
            }
            RouteOperator::GreaterThan => {
                if let (Ok(a), Ok(b)) = (actual.parse::<i64>(), expected.parse::<i64>()) {
                    a > b
                } else {
                    false
                }
            }
            RouteOperator::LessThan => {
                if let (Ok(a), Ok(b)) = (actual.parse::<i64>(), expected.parse::<i64>()) {
                    a < b
                } else {
                    false
                }
            }
        }
    }
}

impl Default for MessageRouter {
    fn default() -> Self {
        Self::new(
            Arc::new(CollaborationMetrics::new()),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_message() -> AgentMessage {
        use chrono::Utc;
        use super::super::message_bus::MessageType;
        
        AgentMessage {
            id: "msg_1".to_string(),
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            message_type: MessageType::Request,
            content: "test content".to_string(),
            context: HashMap::new(),
            timestamp: Utc::now(),
            correlation_id: None,
        }
    }

    #[tokio::test]
    async fn test_router_creation() {
        let router = MessageRouter::new(
            Arc::new(CollaborationMetrics::new()),
        );
        
        let routes = router.list_all_routes().await;
        assert!(routes.is_empty());
    }

    #[tokio::test]
    async fn test_add_route() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![],
            enabled: true,
        };
        
        let result = router.add_route(rule).await;
        assert!(result.is_ok());
        
        let routes = router.list_routes("agent_1").await;
        assert_eq!(routes.len(), 1);
    }

    #[tokio::test]
    async fn test_remove_route() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![],
            enabled: true,
        };
        
        router.add_route(rule).await;
        router.remove_route("agent_1", "agent_2").await;
        
        let routes = router.list_routes("agent_1").await;
        assert!(routes.is_empty());
    }

    #[tokio::test]
    async fn test_route_with_matching_condition() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![
                RouteCondition {
                    field: "message_type".to_string(),
                    operator: RouteOperator::Equals,
                    value: "Request".to_string(),
                },
            ],
            enabled: true,
        };
        
        router.add_route(rule).await;
        
        let message = create_test_message();
        let result = router.route(&message).await;
        
        assert!(result.is_some());
    }

    #[tokio::test]
    async fn test_route_with_non_matching_condition() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![
                RouteCondition {
                    field: "message_type".to_string(),
                    operator: RouteOperator::Equals,
                    value: "Response".to_string(),
                },
            ],
            enabled: true,
        };
        
        router.add_route(rule).await;
        
        let message = create_test_message();
        let result = router.route(&message).await;
        
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_route_delegation() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![
                RouteCondition {
                    field: "task".to_string(),
                    operator: RouteOperator::Contains,
                    value: "development".to_string(),
                },
            ],
            enabled: true,
        };
        
        router.add_route(rule).await;
        
        let result = router.route_delegation("agent_1", "development task").await;
        
        assert_eq!(result.len(), 1);
        assert_eq!(result[0], "agent_2");
    }

    #[tokio::test]
    async fn test_fallback_agent() {
        let router = MessageRouter::default();
        
        router.set_fallback_agent("agent_1", "fallback_agent".to_string()).await;
        
        let message = create_test_message();
        let result = router.route(&message).await;
        
        assert_eq!(result, Some("fallback_agent".to_string()));
    }

    #[tokio::test]
    async fn test_condition_operators() {
        let router = MessageRouter::default();
        
        assert!(router.evaluate_condition(&RouteOperator::Equals, "test", "test"));
        assert!(!router.evaluate_condition(&RouteOperator::Equals, "test", "other"));
        
        assert!(router.evaluate_condition(&RouteOperator::Contains, "test content", "test"));
        assert!(!router.evaluate_condition(&RouteOperator::Contains, "test content", "foo"));
        
        assert!(router.evaluate_condition(&RouteOperator::StartsWith, "test content", "test"));
        assert!(!router.evaluate_condition(&RouteOperator::StartsWith, "test content", "content"));
        
        assert!(router.evaluate_condition(&RouteOperator::EndsWith, "test content", "content"));
        assert!(!router.evaluate_condition(&RouteOperator::EndsWith, "test content", "test"));
        
        assert!(router.evaluate_condition(&RouteOperator::GreaterThan, "10", "5"));
        assert!(router.evaluate_condition(&RouteOperator::LessThan, "5", "10"));
    }

    #[tokio::test]
    async fn test_clear_routes() {
        let router = MessageRouter::default();
        
        let rule = RouteRule {
            from_agent: "agent_1".to_string(),
            to_agent: "agent_2".to_string(),
            priority: 1,
            conditions: vec![],
            enabled: true,
        };
        
        router.add_route(rule).await;
        router.clear_routes("agent_1").await;
        
        let routes = router.list_routes("agent_1").await;
        assert!(routes.is_empty());
    }
}
