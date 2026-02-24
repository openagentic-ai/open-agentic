//! 向量存储工厂实现 - 符合开闭原则

use async_trait::async_trait;
use openclaw_core::Result;
use std::sync::Arc;
use std::sync::Mutex;

use super::VectorStore;

#[derive(Debug, Clone)]
pub struct BackendConfig {
    pub name: String,
    pub path: Option<std::path::PathBuf>,
    pub url: Option<String>,
    pub collection: Option<String>,
    pub table: Option<String>,
    pub api_key: Option<String>,
    pub dimensions: Option<usize>,
}

impl Default for BackendConfig {
    fn default() -> Self {
        Self {
            name: "memory".to_string(),
            path: None,
            url: None,
            collection: None,
            table: None,
            api_key: None,
            dimensions: Some(1536),
        }
    }
}

#[async_trait]
pub trait VectorStoreFactory: Send + Sync {
    fn name(&self) -> &str;
    async fn create(&self, config: &BackendConfig) -> Result<Arc<dyn VectorStore>>;
    fn supports_backend(&self, name: &str) -> bool {
        self.name() == name
    }
}

pub type FactoryPtr = Arc<dyn VectorStoreFactory>;

static FACTORY_REGISTRY: Mutex<Vec<FactoryPtr>> = Mutex::new(Vec::new());

pub fn register_factory(factory: FactoryPtr) {
    if let Ok(mut registry) = FACTORY_REGISTRY.lock() {
        registry.push(factory);
    }
}

pub fn get_registered_factories() -> Vec<String> {
    FACTORY_REGISTRY
        .lock()
        .map(|f| f.iter().map(|factory| factory.name().to_string()).collect())
        .unwrap_or_default()
}

pub fn get_factory(name: &str) -> Option<FactoryPtr> {
    FACTORY_REGISTRY
        .lock()
        .ok()
        .and_then(|factories| {
            factories
                .iter()
                .find(|f| f.name() == name)
                .cloned()
        })
}

pub fn init_default_factories() {
    register_factory(Arc::new(MemoryStoreFactory) as FactoryPtr);
}

pub struct MemoryStoreFactory;

#[async_trait]
impl VectorStoreFactory for MemoryStoreFactory {
    fn name(&self) -> &str {
        "memory"
    }

    async fn create(&self, _config: &BackendConfig) -> Result<Arc<dyn VectorStore>> {
        Ok(Arc::new(super::MemoryStore::new()) as Arc<dyn VectorStore>)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memory_store_factory_name() {
        let factory = MemoryStoreFactory;
        assert_eq!(factory.name(), "memory");
    }

    #[test]
    fn test_memory_store_factory_supports_backend() {
        let factory = MemoryStoreFactory;
        assert!(factory.supports_backend("memory"));
        assert!(!factory.supports_backend("lancedb"));
    }

    #[test]
    fn test_backend_config_default() {
        let config = BackendConfig::default();
        assert_eq!(config.name, "memory");
        assert_eq!(config.dimensions, Some(1536));
    }

    #[tokio::test]
    async fn test_memory_store_factory_create() {
        let factory = MemoryStoreFactory;
        let config = BackendConfig::default();
        
        let store = factory.create(&config).await;
        assert!(store.is_ok());
    }

    #[tokio::test]
    async fn test_register_and_get_factory() {
        let factory_name = "memory";
        let factory = Arc::new(MemoryStoreFactory) as FactoryPtr;
        
        register_factory(factory);
        
        let retrieved = get_factory(factory_name);
        assert!(retrieved.is_some());
    }

    #[tokio::test]
    async fn test_get_registered_factories() {
        init_default_factories();
        let factories = get_registered_factories();
        assert!(!factories.is_empty());
        assert!(factories.contains(&"memory".to_string()));
    }
}
