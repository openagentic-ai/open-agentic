use std::path::PathBuf;
use std::sync::Arc;

use super::local::LocalSkillManager;
use super::source::{Skill, SkillOrigin, InstalledSkill, SearchResult};
use crate::evo::registry::SharedSkillRegistry;

pub struct SkillManager {
    local: LocalSkillManager,
    hub_client: Option<ClawHubClient>,
    cache_dir: PathBuf,
}

impl SkillManager {
    pub fn new(registry: Arc<SharedSkillRegistry>, cache_dir: PathBuf) -> Self {
        Self {
            local: LocalSkillManager::new(registry, cache_dir.clone()),
            hub_client: None,
            cache_dir,
        }
    }

    pub fn with_default_cache(registry: Arc<SharedSkillRegistry>) -> Self {
        let cache_dir = Self::default_cache_dir();
        Self::new(registry, cache_dir)
    }

    fn default_cache_dir() -> PathBuf {
        let mut path = dirs::data_local_dir().unwrap_or_else(|| PathBuf::from("."));
        path.push("openclaw");
        path.push("skills");
        path
    }

    pub fn with_hub_client(mut self, client: ClawHubClient) -> Self {
        self.hub_client = Some(client);
        self
    }

    pub fn cache_dir(&self) -> &Path {
        &self.cache_dir
    }

    pub async fn initialize(&self) -> crate::Result<()> {
        tokio::fs::create_dir_all(&self.cache_dir).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to create cache dir: {}", e)))?;
        
        let skills = self.local.load_skills_from_cache().await?;
        
        for skill in skills {
            self.local.register_skill(skill).await?;
        }
        
        tracing::info!("SkillManager initialized with cache at {:?}", self.cache_dir);
        Ok(())
    }

    pub async fn install(&self, source: &str) -> crate::Result<Skill> {
        if source.starts_with("http://") || source.starts_with("https://") {
            self.install_from_url(source).await
        } else if PathBuf::from(source).exists() {
            self.install_from_file(source).await
        } else {
            self.install_from_hub(source).await
        }
    }

    pub async fn install_from_file(&self, path: &str) -> crate::Result<Skill> {
        let content = tokio::fs::read_to_string(path).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to read file: {}", e)))?;

        let loader = crate::evo::skill_loader::SkillLoader::new(
            Arc::new(SharedSkillRegistry::new())
        );
        
        let mut dynamic_skill = loader.parse_skill_md(&content)
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse skill: {}", e)))?;

        let skill = Skill::new(dynamic_skill, SkillOrigin::Local);
        
        self.local.register_skill(skill.dynamic_skill.clone()).await?;
        
        let skill_path = self.cache_dir.join(format!("{}.md", skill.name));
        tokio::fs::write(&skill_path, content).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to save to cache: {}", e)))?;
        
        tracing::info!("Installed skill '{}' from file", skill.name);
        Ok(skill)
    }

    pub async fn install_from_hub(&self, name: &str) -> crate::Result<Skill> {
        let client = self.hub_client.as_ref()
            .ok_or_else(|| crate::OpenClawError::Config("ClawHub client not configured".into()))?;

        let hub_skill = client.download_skill(name, "latest").await?;
        
        let loader = crate::evo::skill_loader::SkillLoader::new(
            Arc::new(SharedSkillRegistry::new())
        );
        
        let mut dynamic_skill = loader.parse_skill_md(&hub_skill.content)
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse skill: {}", e)))?;
        
        dynamic_skill.source = crate::evo::registry::SkillSource::User;
        
        let skill = Skill::new(dynamic_skill.clone(), SkillOrigin::ClawHub);
        
        self.local.register_skill(dynamic_skill).await?;
        
        let skill_path = self.cache_dir.join(format!("{}.md", skill.name));
        tokio::fs::write(&skill_path, &hub_skill.content).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to save to cache: {}", e)))?;
        
        tracing::info!("Installed skill '{}' from ClawHub", skill.name);
        Ok(skill)
    }

    async fn install_from_url(&self, url: &str) -> crate::Result<Skill> {
        let response = reqwest::get(url).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to fetch URL: {}", e)))?;
        
        let content = response.text().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to read response: {}", e)))?;
        
        let loader = crate::evo::skill_loader::SkillLoader::new(
            Arc::new(SharedSkillRegistry::new())
        );
        
        let mut dynamic_skill = loader.parse_skill_md(&content)
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse skill: {}", e)))?;
        
        let skill = Skill::new(dynamic_skill.clone(), SkillOrigin::Local);
        
        self.local.register_skill(dynamic_skill).await?;
        
        let skill_path = self.cache_dir.join(format!("{}.md", skill.name));
        tokio::fs::write(&skill_path, &content).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to save to cache: {}", e)))?;
        
        tracing::info!("Installed skill '{}' from URL", skill.name);
        Ok(skill)
    }

    pub async fn uninstall(&self, name: &str) -> crate::Result<()> {
        self.local.unregister_skill(name).await?;
        
        let skill_path = self.cache_dir.join(format!("{}.md", name));
        if skill_path.exists() {
            tokio::fs::remove_file(&skill_path).await
                .map_err(|e| crate::OpenClawError::Config(format!("Failed to remove cached file: {}", e)))?;
        }
        
        tracing::info!("Uninstalled skill '{}'", name);
        Ok(())
    }

    pub async fn update(&self, name: &str) -> crate::Result<Skill> {
        self.uninstall(name).await?;
        self.install_from_hub(name).await
    }

    pub async fn search(&self, query: &str) -> crate::Result<Vec<SearchResult>> {
        let mut results = Vec::new();
        
        if let Some(client) = self.hub_client.as_ref() {
            match client.search(query, 10).await {
                Ok(hub_results) => results.extend(hub_results),
                Err(e) => tracing::warn!("Failed to search ClawHub: {}", e),
            }
        }
        
        Ok(results)
    }

    pub async fn list_installed(&self) -> Vec<InstalledSkill> {
        self.local.list_installed().await
    }

    pub async fn is_installed(&self, name: &str) -> bool {
        self.local.is_installed(name).await
    }
}

use std::path::Path;

#[derive(Debug, Clone)]
pub struct ClawHubClient {
    base_url: String,
    http_client: reqwest::Client,
    api_key: Option<String>,
}

impl ClawHubClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            http_client: reqwest::Client::new(),
            api_key: None,
        }
    }

    pub fn with_api_key(mut self, api_key: impl Into<String>) -> Self {
        self.api_key = Some(api_key.into());
        self
    }

    pub async fn search(&self, query: &str, limit: usize) -> crate::Result<Vec<SearchResult>> {
        let url = format!("{}/api/skills/search?q={}&limit={}", self.base_url, query, limit);
        
        let mut request = self.http_client.get(&url);
        
        if let Some(ref key) = self.api_key {
            request = request.header("Authorization", format!("Bearer {}", key));
        }
        
        let response = request.send().await
            .map_err(|e| crate::OpenClawError::Config(format!("Request failed: {}", e)))?;
        
        if !response.status().is_success() {
            return Err(crate::OpenClawError::Config(
                format!("ClawHub API error: {}", response.status())
            ));
        }
        
        let results: Vec<SearchResult> = response.json().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse response: {}", e)))?;
        
        Ok(results)
    }

    pub async fn download_skill(&self, name: &str, version: &str) -> crate::Result<HubSkillBundle> {
        let url = format!("{}/api/skills/{}/download?version={}", self.base_url, name, version);
        
        let mut request = self.http_client.get(&url);
        
        if let Some(ref key) = self.api_key {
            request = request.header("Authorization", format!("Bearer {}", key));
        }
        
        let response = request.send().await
            .map_err(|e| crate::OpenClawError::Config(format!("Request failed: {}", e)))?;
        
        if !response.status().is_success() {
            return Err(crate::OpenClawError::Config(
                format!("ClawHub API error: {}", response.status())
            ));
        }
        
        let bundle: HubSkillBundle = response.json().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse response: {}", e)))?;
        
        Ok(bundle)
    }

    pub async fn get_skill_info(&self, name: &str) -> crate::Result<HubSkillInfo> {
        let url = format!("{}/api/skills/{}", self.base_url, name);
        
        let mut request = self.http_client.get(&url);
        
        if let Some(ref key) = self.api_key {
            request = request.header("Authorization", format!("Bearer {}", key));
        }
        
        let response = request.send().await
            .map_err(|e| crate::OpenClawError::Config(format!("Request failed: {}", e)))?;
        
        if !response.status().is_success() {
            return Err(crate::OpenClawError::Config(
                format!("ClawHub API error: {}", response.status())
            ));
        }
        
        let info: HubSkillInfo = response.json().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse response: {}", e)))?;
        
        Ok(info)
    }

    pub async fn list_popular(&self, limit: usize) -> crate::Result<Vec<SearchResult>> {
        let url = format!("{}/api/skills/popular?limit={}", self.base_url, limit);
        
        let mut request = self.http_client.get(&url);
        
        if let Some(ref key) = self.api_key {
            request = request.header("Authorization", format!("Bearer {}", key));
        }
        
        let response = request.send().await
            .map_err(|e| crate::OpenClawError::Config(format!("Request failed: {}", e)))?;
        
        if !response.status().is_success() {
            return Err(crate::OpenClawError::Config(
                format!("ClawHub API error: {}", response.status())
            ));
        }
        
        let results: Vec<SearchResult> = response.json().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse response: {}", e)))?;
        
        Ok(results)
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct HubSkillBundle {
    pub name: String,
    pub version: String,
    pub content: String,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct HubSkillInfo {
    pub name: String,
    pub version: String,
    pub description: String,
    pub author: String,
    pub downloads: u64,
    pub rating: f32,
    pub tags: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clawhub_client_creation() {
        let client = ClawHubClient::new("https://api.clawhub.ai");
        assert_eq!(client.base_url, "https://api.clawhub.ai");
    }

    #[test]
    fn test_clawhub_client_with_api_key() {
        let client = ClawHubClient::new("https://api.clawhub.ai")
            .with_api_key("test-key");
        assert!(client.api_key.is_some());
    }

    #[tokio::test]
    async fn test_skill_manager_default_cache_dir() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = SkillManager::with_default_cache(registry);
        
        let cache_dir = manager.cache_dir();
        assert!(cache_dir.to_string_lossy().contains("openclaw"));
    }

    #[tokio::test]
    async fn test_skill_manager_is_installed_empty() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = SkillManager::with_default_cache(registry);
        
        assert!(!manager.is_installed("nonexistent").await);
    }

    #[tokio::test]
    async fn test_skill_manager_list_installed_empty() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = SkillManager::with_default_cache(registry);
        
        let installed = manager.list_installed().await;
        assert!(installed.is_empty());
    }
}
