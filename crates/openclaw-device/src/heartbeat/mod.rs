use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DeviceStatus {
    Online,
    Offline,
    Standby,
    Error,
    Unknown,
}

impl Default for DeviceStatus {
    fn default() -> Self {
        DeviceStatus::Unknown
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceMetrics {
    pub uptime_secs: u64,
    pub cpu_usage_percent: Option<f32>,
    pub memory_usage_percent: Option<f32>,
    pub temperature_celsius: Option<f32>,
    pub battery_percent: Option<u8>,
    pub network_connected: bool,
}

impl Default for DeviceMetrics {
    fn default() -> Self {
        Self {
            uptime_secs: 0,
            cpu_usage_percent: None,
            memory_usage_percent: None,
            temperature_celsius: None,
            battery_percent: None,
            network_connected: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatData {
    pub device_id: String,
    pub provider_name: String,
    pub timestamp: u64,
    pub status: DeviceStatus,
    pub metrics: DeviceMetrics,
    pub custom_fields: HashMap<String, String>,
}

impl HeartbeatData {
    pub fn new(device_id: String, provider_name: String) -> Self {
        Self {
            device_id,
            provider_name,
            timestamp: current_timestamp(),
            status: DeviceStatus::Unknown,
            metrics: DeviceMetrics::default(),
            custom_fields: HashMap::new(),
        }
    }
}

pub trait HeartbeatProvider: Send + Sync {
    fn provider_name(&self) -> &str;
    fn device_id(&self) -> &str;
    fn get_heartbeat_data(&self) -> HeartbeatData;
    fn get_device_status(&self) -> DeviceStatus;
}

pub fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatConfig {
    pub enabled: bool,
    pub interval_secs: u64,
    pub base_topic: String,
    pub qos: u8,
    pub retain: bool,
    pub include_lwt: bool,
    pub lwt_topic: String,
    pub lwt_payload_offline: String,
}

impl Default for HeartbeatConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval_secs: 30,
            base_topic: "devices/{device_id}/heartbeat".to_string(),
            qos: 1,
            retain: false,
            include_lwt: true,
            lwt_topic: "devices/{device_id}/status".to_string(),
            lwt_payload_offline: r#"{"status":"offline"}"#.to_string(),
        }
    }
}

pub fn apply_topic_template(template: &str, device_id: &str) -> String {
    template.replace("{device_id}", device_id)
}

pub fn apply_lwt_template(template: &str, device_id: &str, status: &str) -> String {
    template
        .replace("{device_id}", device_id)
        .replace("{status}", status)
}

pub struct HeartbeatManager {
    providers: Arc<RwLock<HashMap<String, Arc<dyn HeartbeatProvider>>>>,
    config: HeartbeatConfig,
    active_tasks: Arc<RwLock<HashMap<String, tokio::task::JoinHandle<()>>>>,
    start_time: Instant,
}

impl HeartbeatManager {
    pub fn new(config: HeartbeatConfig) -> Self {
        Self {
            providers: Arc::new(RwLock::new(HashMap::new())),
            config,
            active_tasks: Arc::new(RwLock::new(HashMap::new())),
            start_time: Instant::now(),
        }
    }

    pub async fn register_provider(&self, provider: Arc<dyn HeartbeatProvider>) {
        let device_id = provider.device_id().to_string();
        let mut providers = self.providers.write().await;
        providers.insert(device_id, provider);
    }

    pub async fn unregister_provider(&self, device_id: &str) {
        self.stop_for_device(device_id).await;
        let mut providers = self.providers.write().await;
        providers.remove(device_id);
    }

    pub async fn get_providers(&self) -> Vec<Arc<dyn HeartbeatProvider>> {
        let providers = self.providers.read().await;
        providers.values().cloned().collect()
    }

    pub async fn setup_lwt(&self) -> Result<(), HeartbeatError> {
        if !self.config.include_lwt {
            return Ok(());
        }
        Ok(())
    }

    pub fn start_all<F>(&self, mqtt_publisher: F)
    where
        F: Fn(String, Vec<u8>, u8, bool) -> tokio::task::JoinHandle<()> + Send + Sync + 'static,
    {
        if !self.config.enabled {
            return;
        }

        let providers = self.providers.clone();
        let config = self.config.clone();
        let active_tasks = self.active_tasks.clone();
        let start_time = self.start_time;
        let publisher = Arc::new(mqtt_publisher);

        tokio::spawn(async move {
            let provider_list = {
                let p = providers.read().await;
                p.values().cloned().collect::<Vec<_>>()
            };

            for provider in provider_list {
                spawn_heartbeat_task(
                    provider,
                    config.clone(),
                    publisher.clone(),
                    active_tasks.clone(),
                    start_time,
                ).await;
            }
        });
    }

    pub async fn start_for_device<F>(&self, device_id: &str, mqtt_publisher: F)
    where
        F: Fn(String, Vec<u8>, u8, bool) -> tokio::task::JoinHandle<()> + Send + Sync + 'static,
    {
        let provider = {
            let providers = self.providers.read().await;
            providers.get(device_id).cloned()
        };

        if let Some(provider) = provider {
            let publisher = Arc::new(mqtt_publisher);
            spawn_heartbeat_task(
                provider,
                self.config.clone(),
                publisher,
                self.active_tasks.clone(),
                self.start_time,
            ).await;
        }
    }

    pub async fn stop_all(&self) {
        let mut tasks = self.active_tasks.write().await;
        for (_, handle) in tasks.drain() {
            handle.abort();
        }
    }

    pub async fn stop_for_device(&self, device_id: &str) {
        let mut tasks = self.active_tasks.write().await;
        if let Some(handle) = tasks.remove(device_id) {
            handle.abort();
        }
    }

    pub fn is_running(&self, device_id: &str) -> bool {
        if let Ok(tasks) = self.active_tasks.try_read() {
            return tasks.contains_key(device_id);
        }
        false
    }

    pub fn get_uptime(&self) -> Duration {
        self.start_time.elapsed()
    }

    pub fn config(&self) -> &HeartbeatConfig {
        &self.config
    }
}

async fn spawn_heartbeat_task<F>(
    provider: Arc<dyn HeartbeatProvider>,
    config: HeartbeatConfig,
    mqtt_publisher: Arc<F>,
    active_tasks: Arc<RwLock<HashMap<String, tokio::task::JoinHandle<()>>>>,
    _manager_start_time: Instant,
)
where
    F: Fn(String, Vec<u8>, u8, bool) -> tokio::task::JoinHandle<()> + Send + Sync + 'static,
{
    let device_id = provider.device_id().to_string();
    let topic = config.base_topic.replace("{device_id}", &device_id);

    let handle = tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(config.interval_secs));
        
        loop {
            interval.tick().await;
            
            let heartbeat_data = provider.get_heartbeat_data();
            
            let payload = match serde_json::to_string(&heartbeat_data) {
                Ok(p) => p,
                Err(_) => {
                    continue;
                }
            };

            let _ = mqtt_publisher(topic.clone(), payload.into_bytes(), config.qos, config.retain).await;
        }
    });

    let mut tasks = active_tasks.write().await;
    tasks.insert(device_id, handle);
}

#[derive(Debug, thiserror::Error)]
pub enum HeartbeatError {
    #[error("Provider not found: {0}")]
    ProviderNotFound(String),
    
    #[error("MQTT client not configured")]
    MqttNotConfigured,
    
    #[error("Heartbeat task error: {0}")]
    TaskError(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(String),
}

pub mod embedded;
pub mod robot;
pub mod host;

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone)]
    struct MockHeartbeatProvider {
        id: String,
        name: String,
        status: DeviceStatus,
    }

    impl MockHeartbeatProvider {
        fn new(id: &str, name: &str) -> Self {
            Self {
                id: id.to_string(),
                name: name.to_string(),
                status: DeviceStatus::Online,
            }
        }
    }

    impl HeartbeatProvider for MockHeartbeatProvider {
        fn provider_name(&self) -> &str {
            &self.name
        }

        fn device_id(&self) -> &str {
            &self.id
        }

        fn get_heartbeat_data(&self) -> HeartbeatData {
            HeartbeatData::new(self.id.clone(), self.name.clone())
        }

        fn get_device_status(&self) -> DeviceStatus {
            self.status
        }
    }

    fn mock_publisher(_topic: String, _payload: Vec<u8>, _qos: u8, _retain: bool) -> tokio::task::JoinHandle<()> {
        tokio::spawn(async {})
    }

    #[tokio::test]
    async fn test_heartbeat_manager_register() {
        let config = HeartbeatConfig::default();
        let manager = HeartbeatManager::new(config);

        let provider = Arc::new(MockHeartbeatProvider::new("test-device", "test"));
        manager.register_provider(provider).await;

        let providers = manager.get_providers().await;
        assert_eq!(providers.len(), 1);
    }

    #[tokio::test]
    async fn test_heartbeat_manager_unregister() {
        let config = HeartbeatConfig::default();
        let manager = HeartbeatManager::new(config);

        let provider = Arc::new(MockHeartbeatProvider::new("test-device", "test"));
        manager.register_provider(provider).await;
        manager.unregister_provider("test-device").await;

        let providers = manager.get_providers().await;
        assert_eq!(providers.len(), 0);
    }

    #[tokio::test]
    async fn test_heartbeat_manager_disabled() {
        let mut config = HeartbeatConfig::default();
        config.enabled = false;
        let manager = HeartbeatManager::new(config);

        manager.start_all(mock_publisher);

        tokio::time::sleep(Duration::from_millis(100)).await;
        
        assert!(!manager.is_running("any-device"));
    }

    #[test]
    fn test_device_status_default() {
        let status: DeviceStatus = DeviceStatus::default();
        assert_eq!(status, DeviceStatus::Unknown);
    }

    #[test]
    fn test_device_metrics_default() {
        let metrics = DeviceMetrics::default();
        assert_eq!(metrics.uptime_secs, 0);
        assert!(!metrics.network_connected);
    }

    #[test]
    fn test_heartbeat_data_new() {
        let data = HeartbeatData::new("device-001".to_string(), "camera".to_string());
        assert_eq!(data.device_id, "device-001");
        assert_eq!(data.provider_name, "camera");
        assert_eq!(data.status, DeviceStatus::Unknown);
    }

    #[test]
    fn test_heartbeat_config_default() {
        let config = HeartbeatConfig::default();
        assert!(config.enabled);
        assert_eq!(config.interval_secs, 30);
        assert!(config.include_lwt);
    }

    #[test]
    fn test_topic_template() {
        let template = "devices/{device_id}/heartbeat";
        let result = apply_topic_template(template, "cam-001");
        assert_eq!(result, "devices/cam-001/heartbeat");
    }

    #[test]
    fn test_lwt_template() {
        let template = "devices/{device_id}/status";
        let result = apply_lwt_template(template, "cam-001", "offline");
        assert_eq!(result, "devices/cam-001/status");
    }
}
