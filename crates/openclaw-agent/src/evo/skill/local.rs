use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::Utc;

use super::source::{InstalledSkill, SkillOrigin};
use crate::evo::registry::{DynamicSkill, SharedSkillRegistry, SkillSource};

pub struct LocalSkillManager {
    registry: Arc<SharedSkillRegistry>,
    cache_dir: PathBuf,
}

impl LocalSkillManager {
    pub fn new(registry: Arc<SharedSkillRegistry>, cache_dir: PathBuf) -> Self {
        Self { registry, cache_dir }
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

    pub fn cache_dir(&self) -> &Path {
        &self.cache_dir
    }

    pub async fn load_skills_from_cache(&self) -> crate::Result<Vec<DynamicSkill>> {
        let mut loaded = Vec::new();

        if !self.cache_dir.exists() {
            tracing::info!("Skill cache directory does not exist: {:?}", self.cache_dir);
            return Ok(loaded);
        }

        let mut entries = tokio::fs::read_dir(&self.cache_dir).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to read cache dir: {}", e)))?;

        while let Some(entry) = entries.next_entry().await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to read entry: {}", e)))? 
        {
            let path = entry.path();
            if path.extension().map(|e| e == "md").unwrap_or(false) {
                match self.load_skill_file(&path).await {
                    Ok(skill) => loaded.push(skill),
                    Err(e) => tracing::warn!("Failed to load skill from {:?}: {}", path, e),
                }
            }
        }

        tracing::info!("Loaded {} skills from cache", loaded.len());
        Ok(loaded)
    }

    async fn load_skill_file(&self, path: &Path) -> crate::Result<DynamicSkill> {
        let content = tokio::fs::read_to_string(path).await
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to read file: {}", e)))?;

        let loader = crate::evo::skill_loader::SkillLoader::new(Arc::new(SharedSkillRegistry::new()));
        let skill = loader.parse_skill_md(&content)
            .map_err(|e| crate::OpenClawError::Config(format!("Failed to parse skill: {}", e)))?;

        Ok(skill)
    }

    pub async fn register_skill(&self, skill: DynamicSkill) -> crate::Result<()> {
        let mut skill_with_source = skill;
        skill_with_source.source = SkillSource::User;

        self.registry.register_skill(skill_with_source).await;
        tracing::info!("Registered skill from local cache");
        Ok(())
    }

    pub async fn unregister_skill(&self, name: &str) -> crate::Result<DynamicSkill> {
        self.registry.unregister_skill(name).await
    }

    pub async fn list_installed(&self) -> Vec<InstalledSkill> {
        let skills = self.registry.get_all_skills().await;
        
        skills.into_iter().map(|s| InstalledSkill {
            name: s.name,
            version: s.version,
            origin: SkillOrigin::Local,
            installed_at: Utc::now(),
            format: s.format,
        }).collect()
    }

    pub async fn is_installed(&self, name: &str) -> bool {
        self.registry.skill_exists(name).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_local_skill_manager_creation() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = LocalSkillManager::new(registry, PathBuf::from("/tmp/test-skills"));
        
        assert_eq!(manager.cache_dir(), PathBuf::from("/tmp/test-skills"));
    }

    #[tokio::test]
    async fn test_default_cache_dir() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = LocalSkillManager::with_default_cache(registry);
        
        let cache_dir = manager.cache_dir();
        assert!(cache_dir.to_string_lossy().contains("openclaw"));
    }

    #[tokio::test]
    async fn test_is_installed_empty() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = LocalSkillManager::new(registry.clone(), PathBuf::from("/tmp/test"));
        
        assert!(!manager.is_installed("nonexistent").await);
    }

    #[tokio::test]
    async fn test_list_installed_empty() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let manager = LocalSkillManager::new(registry, PathBuf::from("/tmp/test"));
        
        let installed = manager.list_installed().await;
        assert!(installed.is_empty());
    }
}
