//! 账号管理器 - 统一管理多平台账号
//!
//! 支持通过 Skill 动态扩展多账号能力

use std::collections::HashMap;

use tokio::sync::RwLock;

use super::{AccountConfig, AccountId, Platform};

pub struct AccountManager {
    accounts: RwLock<HashMap<AccountId, AccountInstance>>,
    bindings: RwLock<HashMap<String, Vec<AccountId>>>,
    skill_extensions: RwLock<HashMap<Platform, String>>,
}

pub struct AccountInstance {
    pub config: AccountConfig,
    pub platform: Platform,
}

impl AccountManager {
    pub fn new() -> Self {
        Self {
            accounts: RwLock::new(HashMap::new()),
            bindings: RwLock::new(HashMap::new()),
            skill_extensions: RwLock::new(HashMap::new()),
        }
    }

    pub async fn register(&self, config: AccountConfig) {
        let account_id = config.id.clone();
        let instance = AccountInstance {
            config: config.clone(),
            platform: config.platform,
        };

        let mut accounts = self.accounts.write().await;
        accounts.insert(account_id.clone(), instance);

        for agent_id in &config.bound_agents {
            let mut bindings = self.bindings.write().await;
            bindings.entry(agent_id.clone()).or_default().push(account_id.clone());
        }
    }

    pub async fn get_account(&self, account_id: &AccountId) -> Option<AccountConfig> {
        let accounts = self.accounts.read().await;
        accounts.get(account_id).map(|a| a.config.clone())
    }

    pub async fn get_accounts_for_agent(&self, agent_id: &str) -> Vec<AccountConfig> {
        let bindings = self.bindings.read().await;
        let accounts = self.accounts.read().await;

        bindings
            .get(agent_id)
            .map(|ids| {
                ids.iter()
                    .filter_map(|id| accounts.get(id).map(|a| a.config.clone()))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub async fn list_accounts(&self) -> Vec<AccountConfig> {
        let accounts = self.accounts.read().await;
        accounts.values().map(|a| a.config.clone()).collect()
    }

    pub async fn register_skill_extension(&self, platform: Platform, skill_id: String) {
        let mut extensions = self.skill_extensions.write().await;
        extensions.insert(platform, skill_id);
    }

    pub async fn get_skill_extension(&self, platform: &Platform) -> Option<String> {
        let extensions = self.skill_extensions.read().await;
        extensions.get(platform).cloned()
    }

    pub async fn list_skill_extensions(&self) -> Vec<(Platform, String)> {
        let extensions = self.skill_extensions.read().await;
        extensions.iter().map(|(k, v)| (k.clone(), v.clone())).collect()
    }
}

impl Default for AccountManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_account_manager() {
        let manager = AccountManager::new();
        assert!(manager.list_accounts().await.is_empty());
    }
}
