use async_trait::async_trait;
use std::sync::Arc;

use crate::config::DevicesConfig;
use crate::nodes::DeviceError;
use crate::unified_manager::UnifiedDeviceManager;

pub type DeviceResult<T> = Result<T, DeviceError>;

#[async_trait]
pub trait DeviceManagerFactory: Send + Sync {
    fn name(&self) -> &str;
    async fn create(&self, config: &DevicesConfig) -> DeviceResult<Arc<UnifiedDeviceManager>>;
    async fn create_with_registry(
        &self,
        config: &DevicesConfig,
        registry: Arc<crate::registry::DeviceRegistry>,
    ) -> DeviceResult<Arc<UnifiedDeviceManager>>;
}

pub struct DefaultDeviceManagerFactory;

#[async_trait]
impl DeviceManagerFactory for DefaultDeviceManagerFactory {
    fn name(&self) -> &str {
        "default"
    }

    async fn create(&self, config: &DevicesConfig) -> DeviceResult<Arc<UnifiedDeviceManager>> {
        let registry = Arc::new(crate::registry::DeviceRegistry::new());
        self.create_with_registry(config, registry).await
    }

    async fn create_with_registry(
        &self,
        _config: &DevicesConfig,
        registry: Arc<crate::registry::DeviceRegistry>,
    ) -> DeviceResult<Arc<UnifiedDeviceManager>> {
        let manager = UnifiedDeviceManager::new(registry);
        Ok(Arc::new(manager))
    }
}

static FACTORY_REGISTRY: std::sync::Mutex<Vec<Arc<dyn DeviceManagerFactory>>> =
    std::sync::Mutex::new(Vec::new());

pub fn register_factory(factory: Arc<dyn DeviceManagerFactory>) {
    FACTORY_REGISTRY.lock().unwrap().push(factory);
}

pub fn get_factory(name: &str) -> Option<Arc<dyn DeviceManagerFactory>> {
    FACTORY_REGISTRY
        .lock()
        .unwrap()
        .iter()
        .find(|f| f.name() == name)
        .cloned()
}

pub fn list_factories() -> Vec<String> {
    FACTORY_REGISTRY
        .lock()
        .unwrap()
        .iter()
        .map(|f| f.name().to_string())
        .collect()
}

pub fn init_default_factory() {
    let factory = Arc::new(DefaultDeviceManagerFactory) as Arc<dyn DeviceManagerFactory>;
    register_factory(factory);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_get_factory() {
        let factory = Arc::new(DefaultDeviceManagerFactory);
        register_factory(factory.clone());
        
        let retrieved = get_factory("default");
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().name(), "default");
    }

    #[test]
    fn test_list_factories() {
        let factories = list_factories();
        assert!(!factories.is_empty());
    }

    #[tokio::test]
    async fn test_default_factory_create() {
        let factory = DefaultDeviceManagerFactory;
        let config = DevicesConfig::default();
        
        let manager = factory.create(&config).await;
        assert!(manager.is_ok());
    }
}
