//! Leak Detector Service - 泄露检测服务
//!
//! 提供敏感信息泄露检测和脱敏

use async_trait::async_trait;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;

#[derive(Debug, Error)]
pub enum LeakError {
    #[error("Invalid pattern: {0}")]
    InvalidPattern(String),
    
    #[error("Detection failed: {0}")]
    DetectionFailed(String),
    
    #[error("Storage error: {0}")]
    StorageError(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Severity {
    Info = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensitivePattern {
    pub name: String,
    pub pattern: String,
    pub severity: Severity,
    pub enabled: bool,
    #[serde(skip)]
    compiled_regex: Option<regex::Regex>,
}

impl PartialEq for SensitivePattern {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name
    }
}

impl Eq for SensitivePattern {}

impl Hash for SensitivePattern {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.name.hash(state);
    }
}

impl SensitivePattern {
    pub fn new(name: &str, pattern: &str, severity: Severity) -> Result<Self, LeakError> {
        let compiled = Regex::new(pattern).ok();
        Ok(Self {
            name: name.to_string(),
            pattern: pattern.to_string(),
            severity,
            enabled: true,
            compiled_regex: compiled,
        })
    }
    
    pub fn matches(&self, text: &str) -> bool {
        if !self.enabled {
            return false;
        }
        if let Some(ref re) = self.compiled_regex {
            return re.is_match(text);
        }
        Regex::new(&self.pattern)
            .map(|re| re.is_match(text))
            .unwrap_or(false)
    }
}

#[derive(Debug, Clone)]
pub struct LeakDetection {
    pub pattern_name: String,
    pub severity: Severity,
    pub matched_text: String,
    pub start: usize,
    pub end: usize,
}

#[derive(Debug, Clone, Default)]
pub struct LeakResult {
    pub detections: Vec<LeakDetection>,
    pub is_leaked: bool,
    pub severity: Option<Severity>,
}

impl LeakResult {
    pub fn clean() -> Self {
        Self::default()
    }
    
    pub fn with_detection(mut self, detection: LeakDetection) -> Self {
        self.is_leaked = true;
        if self.severity.is_none() || detection.severity > self.severity.unwrap() {
            self.severity = Some(detection.severity);
        }
        self.detections.push(detection);
        self
    }
}

#[async_trait]
pub trait LeakDetector: Send + Sync {
    fn detect(&self, text: &str) -> LeakResult;
    
    fn detect_and_redact(&self, text: &str) -> (String, LeakResult);
    
    async fn add_pattern(&self, pattern: SensitivePattern) -> Result<(), LeakError>;
    
    async fn remove_pattern(&self, name: &str) -> Result<(), LeakError>;
    
    async fn enable_pattern(&self, name: &str) -> Result<(), LeakError>;
    
    async fn disable_pattern(&self, name: &str) -> Result<(), LeakError>;
    
    async fn list_patterns(&self) -> Vec<SensitivePattern>;
}

pub struct RegexLeakDetector {
    patterns: Arc<RwLock<HashMap<String, SensitivePattern>>>,
}

impl Default for RegexLeakDetector {
    fn default() -> Self {
        Self::new()
    }
}

impl RegexLeakDetector {
    pub fn new() -> Self {
        Self {
            patterns: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub fn with_patterns(patterns: HashMap<String, SensitivePattern>) -> Self {
        Self {
            patterns: Arc::new(RwLock::new(patterns)),
        }
    }
    
    fn detect_with_patterns(&self, patterns: &HashMap<String, SensitivePattern>, text: &str) -> LeakResult {
        let mut result = LeakResult::default();
        
        for pattern in patterns.values() {
            if !pattern.enabled {
                continue;
            }
            if let Some(ref re) = pattern.compiled_regex {
                for mat in re.find_iter(text) {
                    result = result.with_detection(LeakDetection {
                        pattern_name: pattern.name.clone(),
                        severity: pattern.severity,
                        matched_text: mat.as_str().to_string(),
                        start: mat.start(),
                        end: mat.end(),
                    });
                }
            } else if let Ok(re) = Regex::new(&pattern.pattern) {
                for mat in re.find_iter(text) {
                    result = result.with_detection(LeakDetection {
                        pattern_name: pattern.name.clone(),
                        severity: pattern.severity,
                        matched_text: mat.as_str().to_string(),
                        start: mat.start(),
                        end: mat.end(),
                    });
                }
            }
        }
        
        result
    }
    
    fn get_patterns_sync(&self) -> HashMap<String, SensitivePattern> {
        if let Ok(guard) = self.patterns.try_read() {
            return guard.clone();
        }
        
        self.patterns.blocking_read().clone()
    }
}

#[async_trait]
impl LeakDetector for RegexLeakDetector {
    fn detect(&self, text: &str) -> LeakResult {
        let patterns = self.get_patterns_sync();
        self.detect_with_patterns(&patterns, text)
    }
    
    fn detect_and_redact(&self, text: &str) -> (String, LeakResult) {
        let patterns = self.get_patterns_sync();
        let result = self.detect_with_patterns(&patterns, text);
        let mut redacted = text.to_string();
        
        for detection in &result.detections {
            let replacement = match detection.severity {
                Severity::Critical | Severity::High => "[REDACTED]",
                Severity::Medium => "[SENSITIVE]",
                Severity::Low | Severity::Info => "[CONTACT]",
            };
            redacted = redacted.replace(&detection.matched_text, replacement);
        }
        
        (redacted, result)
    }
    
    async fn add_pattern(&self, pattern: SensitivePattern) -> Result<(), LeakError> {
        let mut patterns = self.patterns.write().await;
        patterns.insert(pattern.name.clone(), pattern);
        Ok(())
    }
    
    async fn remove_pattern(&self, name: &str) -> Result<(), LeakError> {
        let mut patterns = self.patterns.write().await;
        patterns.remove(name);
        Ok(())
    }
    
    async fn enable_pattern(&self, name: &str) -> Result<(), LeakError> {
        let mut patterns = self.patterns.write().await;
        if let Some(pattern) = patterns.get_mut(name) {
            pattern.enabled = true;
        }
        Ok(())
    }
    
    async fn disable_pattern(&self, name: &str) -> Result<(), LeakError> {
        let mut patterns = self.patterns.write().await;
        if let Some(pattern) = patterns.get_mut(name) {
            pattern.enabled = false;
        }
        Ok(())
    }
    
    async fn list_patterns(&self) -> Vec<SensitivePattern> {
        let patterns = self.patterns.read().await;
        patterns.values().cloned().collect()
    }
}

pub fn create_default_detector() -> RegexLeakDetector {
    let default_patterns: Vec<SensitivePattern> = vec![
        SensitivePattern::new("api_key", r#"(?i)["\x22]?(api[_-]?key|apikey|api_secret|api-secret)["\x22]?\s*[:=]\s*["\x22]?[\w-]{16,}["\x22]?"#, Severity::Critical).unwrap(),
        SensitivePattern::new("aws_key", r#"(?i)["\x22]?(aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret[_-]?access[_-]?key)["\x22]?\s*[:=]\s*["\x22]?[\w/+=]{16,}["\x22]?"#, Severity::Critical).unwrap(),
        SensitivePattern::new("private_key", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", Severity::Critical).unwrap(),
        SensitivePattern::new("password", r#"(?i)["\x22]?(password|passwd|pwd)["\x22]?\s*[:=]\s*["\x22]?[^\s\x22]{8,}["\x22]?"#, Severity::High).unwrap(),
        SensitivePattern::new("jwt", r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+", Severity::High).unwrap(),
        SensitivePattern::new("github_token", r"(?i)(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", Severity::Critical).unwrap(),
        SensitivePattern::new("credit_card", r"\b(?:\d{4}[-\s]?){3}\d{4}\b", Severity::Critical).unwrap(),
        SensitivePattern::new("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", Severity::Low).unwrap(),
        SensitivePattern::new("phone", r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", Severity::Low).unwrap(),
        SensitivePattern::new("ssn", r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", Severity::Critical).unwrap(),
    ];
    
    let mut patterns = HashMap::new();
    for pattern in default_patterns {
        patterns.insert(pattern.name.clone(), pattern);
    }
    
    RegexLeakDetector::with_patterns(patterns)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_pattern_matches() {
        let pattern = SensitivePattern::new("test", r"\d+", Severity::Medium).unwrap();
        assert!(pattern.matches("abc123def"));
        assert!(!pattern.matches("abcdef"));
    }
    
    #[tokio::test]
    async fn test_api_key_detection() {
        let detector = create_default_detector();
        
        let result = detector.detect(r#"api_key = "sk-1234567890abcdef""#);
        assert!(result.is_leaked);
    }
    
    #[tokio::test]
    async fn test_password_detection() {
        let detector = create_default_detector();
        
        let result = detector.detect(r#"password: "MySecretPass123""#);
        assert!(result.is_leaked);
    }
    
    #[tokio::test]
    async fn test_no_leak() {
        let detector = create_default_detector();
        
        let result = detector.detect("This is just normal text without any secrets.");
        assert!(!result.is_leaked);
    }
    
    #[tokio::test]
    async fn test_redact() {
        let detector = create_default_detector();
        
        let (redacted, result) = detector.detect_and_redact(
            r#"api_key = "sk-1234567890abcdef""#
        );
        
        assert!(result.is_leaked);
        assert!(!redacted.contains("sk-1234567890"));
    }
    
    #[tokio::test]
    async fn test_add_pattern() {
        let detector = RegexLeakDetector::new();
        
        let pattern = SensitivePattern::new("custom", r"CUSTOM\d+", Severity::Medium).unwrap();
        detector.add_pattern(pattern).await.unwrap();
        
        let patterns = detector.list_patterns().await;
        assert!(patterns.iter().any(|p| p.name == "custom"));
    }
    
    #[tokio::test]
    async fn test_disable_pattern() {
        let detector = create_default_detector();
        
        detector.disable_pattern("api_key").await.unwrap();
        
        let result = detector.detect(r#"api_key = "sk-1234567890abcdef""#);
        assert!(!result.is_leaked);
    }
    
    #[tokio::test]
    async fn test_remove_pattern() {
        let detector = create_default_detector();
        
        detector.remove_pattern("api_key").await.unwrap();
        
        let result = detector.detect(r#"api_key = "sk-1234567890abcdef""#);
        assert!(!result.is_leaked);
    }
    
    #[tokio::test]
    async fn test_jwt_detection() {
        let detector = create_default_detector();
        
        let jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
        let result = detector.detect(jwt);
        
        assert!(result.is_leaked);
    }
}
