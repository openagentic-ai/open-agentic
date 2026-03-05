//! OpenClaw Device - 设备节点模块
//!
//! 提供设备能力节点：相机、屏幕录制、定位、通知、系统命令等
//! 以及弹性计算和边缘计算的设备抽象层
//!
//! ## 模块架构
//!
//! - **平台层**: Platform 检测和分类
//! - **设备层**: Device/Adapter 抽象
//! - **HAL 层**: GPIO/I2C/SPI/Serial 硬件抽象
//! - **框架层**: ROS2/MQTT/CAN 协议集成

use std::sync::Arc;

pub mod camera;
pub mod location;
pub mod nodes;
pub mod notification;
pub mod screen;
pub mod system;

pub mod adapter;
pub mod capabilities;
pub mod config;
pub mod device;
pub mod device_trait;
pub mod factory;
pub mod embedded;
pub mod platform;
pub mod registry;

pub mod hal;

pub mod framework;

pub mod modules;

pub mod unified_manager;

pub mod heartbeat;

pub use registry::DeviceRegistry;
pub use unified_manager::UnifiedDeviceManager;
pub use capabilities::DeviceCapabilities;
pub use registry::DeviceHandle;
pub use config::DevicesConfig;
pub use config::CustomDeviceConfig;
pub use platform::Platform;
pub use platform::ComputeCategory;
pub use device::DeviceStatus;

pub use heartbeat::{
    HeartbeatConfig, HeartbeatData, HeartbeatManager, HeartbeatProvider, DeviceMetrics,
    apply_topic_template, apply_lwt_template, HeartbeatError,
    embedded::{Esp32HeartbeatProvider, Stm32HeartbeatProvider, RiscVHeartbeatProvider},
    robot::{JetsonHeartbeatProvider, Ros2HeartbeatProvider},
    host::{CameraHeartbeatProvider, ScreenHeartbeatProvider, LocationHeartbeatProvider},
};
pub use device_trait::DeviceConfig;
pub use device_trait::DeviceBuilder;
pub use unified_manager::DeviceInfo;
pub use camera::CameraManager;
pub use screen::ScreenManager;
pub use nodes::{NodeManager, DeviceNode, NodeStatus, DeviceCapability, DeviceCategory};
pub use notification::{NotificationManager, RichNotification, NotificationCategory, NotificationUrgency};
pub use system::{SystemManager, SystemInfo, CpuInfo, MemoryInfo, DiskInfo};
pub use capabilities::SensorType;
pub use unified_manager::DeviceType;

static DEVICE_REGISTRY: std::sync::OnceLock<Arc<registry::DeviceRegistry>> =
    std::sync::OnceLock::new();

pub async fn init_device(print_info: bool) -> anyhow::Result<()> {
    if let Some(registry) = DEVICE_REGISTRY.get() {
        if print_info {
            let info = registry.platform_info();
            let caps = registry.capabilities();
            println!("Device already initialized");
            println!("Platform: {:?} ({})", info.platform, info.os);
            println!("CPU Cores: {}", caps.cpu.cores);
            println!("Memory: {:.1} GB", caps.memory.total_bytes as f64 / 1e9);
        }
        return Ok(());
    }

    let registry = Arc::new(registry::DeviceRegistry::new());
    registry.init().await?;

    DEVICE_REGISTRY
        .set(registry.clone())
        .map_err(|_| anyhow::anyhow!("Device already initialized"))?;

    let info = registry.platform_info();
    let caps = registry.capabilities();

    if print_info {
        println!();
        println!("╔══════════════════════════════════════════════════════════════════╗");
        println!("║                     OpenClaw Device Info                      ║");
        println!("╠══════════════════════════════════════════════════════════════════╣");
        println!("║  Platform:   {:-56} ║", format!("{:?}", info.platform));
        println!("║  Category:   {:-56} ║", format!("{:?}", info.category));
        println!("║  OS:        {:-56} ║", info.os);
        println!("║  Arch:      {:-56} ║", info.arch);
        println!("╠══════════════════════════════════════════════════════════════════╣");
        println!("║  CPU Cores: {:-56} ║", caps.cpu.cores);
        println!("║  CPU Arch:  {:-56} ║", caps.cpu.architecture);
        println!(
            "║  CPU Freq:  {:-56} ║",
            format!("{} MHz", caps.cpu.frequency_mhz)
        );
        println!(
            "║  Memory:    {:-56} ║",
            format!("{:.1} GB", caps.memory.total_bytes as f64 / 1e9)
        );
        println!(
            "║  Available: {:-56} ║",
            format!("{:.1} GB", caps.memory.available_bytes as f64 / 1e9)
        );
        println!("╠══════════════════════════════════════════════════════════════════╣");

        let mut net_str = String::new();
        let mut net_first = true;
        if caps.network.has_ethernet {
            net_str.push_str("Ethernet");
            net_first = false;
        }
        if caps.network.has_wifi {
            if !net_first {
                net_str.push_str(", ");
            }
            net_str.push_str("WiFi");
            net_first = false;
        }
        if caps.network.has_ble {
            if !net_first {
                net_str.push_str(", ");
            }
            net_str.push_str("BLE");
            net_first = false;
        }
        if caps.network.has_cellular {
            if !net_first {
                net_str.push_str(", ");
            }
            net_str.push_str("Cellular");
        }
        if net_str.is_empty() {
            net_str.push_str("None");
        }
        println!("║  Network:   {:-56} ║", &net_str);

        println!("╠══════════════════════════════════════════════════════════════════╣");
        let mut gpu_str = String::new();
        if caps.gpu.has_gpu {
            gpu_str.push_str(caps.gpu.gpu_name.as_deref().unwrap_or("Available"));
        } else if caps.gpu.has_npu {
            gpu_str.push_str("NPU Available");
        } else {
            gpu_str.push_str("None");
        }
        println!("║  GPU:       {:-56} ║", &gpu_str);

        println!("╠══════════════════════════════════════════════════════════════════╣");
        let mut feat_str = String::new();
        let mut feat_first = true;
        if caps.features.is_container {
            feat_str.push_str("Container");
            feat_first = false;
        }
        if caps.features.is_wasm {
            if !feat_first {
                feat_str.push_str(", ");
            }
            feat_str.push_str("WASM");
            feat_first = false;
        }
        if caps.features.is_virtualized {
            if !feat_first {
                feat_str.push_str(", ");
            }
            feat_str.push_str("Virtualized");
            feat_first = false;
        }
        if caps.features.has_sgx {
            if !feat_first {
                feat_str.push_str(", ");
            }
            feat_str.push_str("SGX");
            feat_first = false;
        }
        if caps.features.has_tpm {
            if !feat_first {
                feat_str.push_str(", ");
            }
            feat_str.push_str("TPM");
            feat_first = false;
        }
        if caps.features.has_npu {
            if !feat_first {
                feat_str.push_str(", ");
            }
            feat_str.push_str("NPU");
        }
        if feat_str.is_empty() {
            feat_str.push_str("None");
        }
        println!("║  Features:  {:-56} ║", &feat_str);
        println!("╚══════════════════════════════════════════════════════════════════╝");
        println!();
    }

    tracing::info!(
        "Device initialized: platform={:?}, category={:?}",
        info.platform,
        info.category
    );

    Ok(())
}

pub async fn get_or_init_device(print_on_init: bool) -> anyhow::Result<Arc<registry::DeviceRegistry>> {
    if let Some(registry) = DEVICE_REGISTRY.get() {
        return Ok(registry.clone());
    }
    
    init_device(print_on_init).await?;
    Ok(DEVICE_REGISTRY.get().unwrap().clone())
}

pub fn get_device_registry() -> Option<Arc<registry::DeviceRegistry>> {
    DEVICE_REGISTRY.get().cloned()
}

pub fn get_or_init_global_registry() -> &'static Arc<registry::DeviceRegistry> {
    DEVICE_REGISTRY.get_or_init(|| Arc::new(registry::DeviceRegistry::new()))
}

#[deprecated(since = "0.1.0", note = "Use get_or_init_global_registry() and call init() manually, or use init_device() for full initialization")]
pub fn get_uninitialized_global_registry() -> &'static Arc<registry::DeviceRegistry> {
    get_or_init_global_registry()
}

pub fn create_device_registry() -> Arc<registry::DeviceRegistry> {
    Arc::new(registry::DeviceRegistry::new())
}

pub async fn get_adapter_config() -> anyhow::Result<adapter::AdapterConfig> {
    let registry = DEVICE_REGISTRY
        .get()
        .ok_or_else(|| anyhow::anyhow!("Device not initialized"))?;

    adapter::Adapters::apply_all(&registry.platform_info().platform, registry.capabilities())
        .await
        .map_err(|e| anyhow::anyhow!("Adapter error: {}", e))
}
