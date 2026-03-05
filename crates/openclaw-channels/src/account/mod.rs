//! 账号模块 - 通用多账号系统

use serde::{Deserialize, Serialize};
use std::fmt;
use std::hash::{Hash, Hasher};

pub mod manager;

pub use manager::AccountManager;

#[derive(Clone, Debug, Serialize, Deserialize, Eq)]
pub struct AccountId(pub String);

impl AccountId {
    pub fn new(id: impl Into<String>) -> Self {
        Self(id.into())
    }
}

impl PartialEq for AccountId {
    fn eq(&self, other: &Self) -> bool {
        self.0 == other.0
    }
}

impl Hash for AccountId {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.0.hash(state);
    }
}

impl fmt::Display for AccountId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Platform {
    Telegram,
    Discord,
    Slack,
    Teams,
    WhatsApp,
    Signal,
    Zalo,
    DingTalk,
    WeCom,
    Feishu,
    Custom(String),
}

impl Platform {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "telegram" => Some(Self::Telegram),
            "discord" => Some(Self::Discord),
            "slack" => Some(Self::Slack),
            "teams" => Some(Self::Teams),
            "whatsapp" => Some(Self::WhatsApp),
            "signal" => Some(Self::Signal),
            "zalo" => Some(Self::Zalo),
            "dingtalk" => Some(Self::DingTalk),
            "wecom" => Some(Self::WeCom),
            "feishu" => Some(Self::Feishu),
            other => Some(Self::Custom(other.to_string())),
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Telegram => "telegram",
            Self::Discord => "discord",
            Self::Slack => "slack",
            Self::Teams => "teams",
            Self::WhatsApp => "whatsapp",
            Self::Signal => "signal",
            Self::Zalo => "zalo",
            Self::DingTalk => "dingtalk",
            Self::WeCom => "wecom",
            Self::Feishu => "feishu",
            Self::Custom(_) => "custom",
        }
    }
}

impl fmt::Display for Platform {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Credentials {
    BotToken { token: String },
    AppCredentials { app_id: String, app_secret: String },
    Webhook { url: String, secret: Option<String> },
    ApiKey { key: String },
}

impl Credentials {
    pub fn validate(&self) -> bool {
        match self {
            Self::BotToken { token } => !token.is_empty(),
            Self::AppCredentials { app_id, app_secret } => {
                !app_id.is_empty() && !app_secret.is_empty()
            }
            Self::Webhook { url, .. } => !url.is_empty(),
            Self::ApiKey { key, .. } => !key.is_empty(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountConfig {
    pub id: AccountId,
    pub name: String,
    pub platform: Platform,
    pub enabled: bool,
    #[serde(default)]
    pub bound_agents: Vec<String>,
    #[serde(flatten)]
    pub credentials: Credentials,
}

impl AccountConfig {
    pub fn new(
        id: AccountId,
        name: String,
        platform: Platform,
        credentials: Credentials,
    ) -> Self {
        Self {
            id,
            name,
            platform,
            enabled: true,
            bound_agents: Vec::new(),
            credentials,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_account_id() {
        let id = AccountId::new("test");
        assert_eq!(id.0, "test");
    }

    #[test]
    fn test_platform_from_str() {
        assert_eq!(Platform::from_str("telegram"), Some(Platform::Telegram));
        assert_eq!(Platform::from_str("feishu"), Some(Platform::Feishu));
    }

    #[test]
    fn test_credentials_validate() {
        assert!(Credentials::BotToken { token: "test".to_string() }.validate());
        assert!(!Credentials::BotToken { token: "".to_string() }.validate());
    }
}
