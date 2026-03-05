use crate::nodes::{DeviceError, SystemCommandResult};
use std::process::Command;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone)]
pub struct SystemInfo {
    pub os_name: String,
    pub os_version: String,
    pub hostname: String,
    pub uptime_seconds: u64,
    pub cpu_count: usize,
    pub cpu_model: String,
    pub total_memory_mb: u64,
    pub available_memory_mb: u64,
    pub total_disk_gb: u64,
    pub available_disk_gb: u64,
}

#[derive(Debug, Clone)]
pub struct CpuInfo {
    pub usage_percent: f32,
    pub user_percent: f32,
    pub system_percent: f32,
    pub idle_percent: f32,
}

#[derive(Debug, Clone)]
pub struct MemoryInfo {
    pub total_mb: u64,
    pub available_mb: u64,
    pub used_mb: u64,
    pub usage_percent: f32,
}

#[derive(Debug, Clone)]
pub struct DiskInfo {
    pub total_gb: u64,
    pub available_gb: u64,
    pub used_gb: u64,
    pub usage_percent: f32,
    pub mount_point: String,
}

#[derive(Debug, Clone)]
pub struct NetworkInfo {
    pub interface_name: String,
    pub bytes_sent: u64,
    pub bytes_recv: u64,
    pub packets_sent: u64,
    pub packets_recv: u64,
}

pub struct SystemManager {
    allowed_commands: Arc<RwLock<Vec<String>>>,
}

impl SystemManager {
    pub fn new() -> Self {
        let allowed = vec![
            "echo".to_string(),
            "date".to_string(),
            "whoami".to_string(),
            "pwd".to_string(),
            "ls".to_string(),
            "cat".to_string(),
            "mkdir".to_string(),
            "touch".to_string(),
            "rm".to_string(),
            "cp".to_string(),
            "mv".to_string(),
        ];

        Self {
            allowed_commands: Arc::new(RwLock::new(allowed)),
        }
    }

    pub async fn run_command(
        &self,
        command: &str,
        args: Vec<String>,
    ) -> Result<SystemCommandResult, DeviceError> {
        let allowed = self.allowed_commands.read().await;

        if !allowed.contains(&command.to_string()) {
            return Ok(SystemCommandResult {
                success: false,
                stdout: None,
                stderr: None,
                exit_code: None,
                error: Some(format!("命令 '{}' 未被允许", command)),
            });
        }

        let output = Command::new(command)
            .args(&args)
            .output()
            .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;

        Ok(SystemCommandResult {
            success: output.status.success(),
            stdout: Some(String::from_utf8_lossy(&output.stdout).to_string()),
            stderr: Some(String::from_utf8_lossy(&output.stderr).to_string()),
            exit_code: output.status.code(),
            error: None,
        })
    }

    pub async fn add_allowed_command(&self, command: String) {
        let mut allowed = self.allowed_commands.write().await;
        if !allowed.contains(&command) {
            allowed.push(command);
        }
    }

    pub async fn remove_allowed_command(&self, command: &str) {
        let mut allowed = self.allowed_commands.write().await;
        allowed.retain(|c| c != command);
    }

    pub async fn list_allowed_commands(&self) -> Vec<String> {
        self.allowed_commands.read().await.clone()
    }

    pub async fn get_system_info(&self) -> Result<SystemInfo, DeviceError> {
        #[cfg(target_os = "macos")]
        {
            let os_name = "macOS".to_string();
            let os_version = self.run_command("sw_vers", vec!["-productVersion".to_string()]).await?
                .stdout.unwrap_or_default().trim().to_string();
            let hostname = self.run_command("hostname", vec![]).await?
                .stdout.unwrap_or_default().trim().to_string();
            let uptime_seconds = self.get_macos_uptime().await?;
            let cpu_count = self.run_command("sysctl", vec!["-n".to_string(), "hw.ncpu".to_string()]).await?
                .stdout.unwrap_or_default().trim().parse().unwrap_or(1);
            let cpu_model = self.run_command("sysctl", vec!["-n".to_string(), "machdep.cpu.brand_string".to_string()]).await?
                .stdout.unwrap_or_default().trim().to_string();
            let (total_memory_mb, available_memory_mb) = self.get_macos_memory().await?;
            let (total_disk_gb, available_disk_gb) = self.get_macos_disk().await?;

            Ok(SystemInfo {
                os_name,
                os_version,
                hostname,
                uptime_seconds,
                cpu_count,
                cpu_model,
                total_memory_mb,
                available_memory_mb,
                total_disk_gb,
                available_disk_gb,
            })
        }

        #[cfg(target_os = "linux")]
        {
            let os_name = std::fs::read_to_string("/etc/os-release")
                .map(|s| {
                    s.lines()
                        .find(|l| l.starts_with("PRETTY_NAME="))
                        .map(|l| l.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string())
                        .unwrap_or_else(|| "Linux".to_string())
                })
                .unwrap_or_else(|_| "Linux".to_string());
            let os_version = std::fs::read_to_string("/proc/version")
                .map(|s| s.trim().to_string())
                .unwrap_or_default();
            let hostname = std::hostname::to_string();
            let uptime_seconds = self.get_linux_uptime().await?;
            let cpu_count = std::fs::read_to_string("/proc/cpuinfo")
                .map(|s| s.lines().filter(|l| l.starts_with("processor")).count())
                .unwrap_or(1);
            let cpu_model = std::fs::read_to_string("/proc/cpuinfo")
                .map(|s| {
                    s.lines()
                        .find(|l| l.starts_with("model name"))
                        .map(|l| l.split(':').nth(1).map(|s| s.trim().to_string()).unwrap_or_default())
                        .unwrap_or_default()
                })
                .unwrap_or_default();
            let (total_memory_mb, available_memory_mb) = self.get_linux_memory().await?;
            let (total_disk_gb, available_disk_gb) = self.get_linux_disk().await?;

            Ok(SystemInfo {
                os_name,
                os_version,
                hostname,
                uptime_seconds,
                cpu_count,
                cpu_model,
                total_memory_mb,
                available_memory_mb,
                total_disk_gb,
                available_disk_gb,
            })
        }

        #[cfg(target_os = "windows")]
        {
            let os_name = "Windows".to_string();
            let os_version = self.run_command("cmd", vec!["/c".to_string(), "ver".to_string()]).await?
                .stdout.unwrap_or_default().trim().to_string();
            let hostname = std::hostname::to_string();
            let uptime_seconds = 0u64;
            let cpu_count = self.run_command("cmd", vec!["/c".to_string(), "echo %NUMBER_OF_PROCESSORS%".to_string()]).await?
                .stdout.unwrap_or_default().trim().parse().unwrap_or(1);
            let cpu_model = "Unknown".to_string();
            let (total_memory_mb, available_memory_mb) = (0, 0);
            let (total_disk_gb, available_disk_gb) = self.get_windows_disk().await?;

            Ok(SystemInfo {
                os_name,
                os_version,
                hostname,
                uptime_seconds,
                cpu_count,
                cpu_model,
                total_memory_mb,
                available_memory_mb,
                total_disk_gb,
                available_disk_gb,
            })
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
        {
            Err(DeviceError::UnsupportedPlatform("Unknown".to_string()))
        }
    }

    #[cfg(target_os = "macos")]
    async fn get_macos_uptime(&self) -> Result<u64, DeviceError> {
        let output = self.run_command("sysctl", vec!["-n".to_string(), "kern.boottime".to_string()]).await?;
        let stdout = output.stdout.unwrap_or_default();
        
        if let Some(ts) = stdout.trim().parse::<u64>().ok() {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);
            Ok(now.saturating_sub(ts))
        } else {
            Ok(0)
        }
    }

    #[cfg(target_os = "macos")]
    async fn get_macos_memory(&self) -> Result<(u64, u64), DeviceError> {
        let output = self.run_command("vm_stat", vec![]).await?;
        let stdout = output.stdout.unwrap_or_default();
        
        let mut pages_free = 0u64;
        let mut pages_active = 0u64;
        let mut pages_inactive = 0u64;
        
        for line in stdout.lines() {
            if line.contains("Pages free:") {
                pages_free = Self::extract_number(line);
            } else if line.contains("Pages active:") {
                pages_active = Self::extract_number(line);
            } else if line.contains("Pages inactive:") {
                pages_inactive = Self::extract_number(line);
            }
        }
        
        let page_size = 4096u64;
        let total = (pages_free + pages_active + pages_inactive) * page_size / 1024 / 1024;
        let available = (pages_free + pages_inactive) * page_size / 1024 / 1024;
        
        Ok((total, available))
    }

    #[cfg(target_os = "macos")]
    async fn get_macos_disk(&self) -> Result<(u64, u64), DeviceError> {
        let output = self.run_command("df", vec!["-k".to_string(), "/".to_string()]).await?;
        let stdout = output.stdout.unwrap_or_default();
        
        for line in stdout.lines().skip(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 4 {
                let total = parts[1].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                let available = parts[3].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                return Ok((total, available));
            }
        }
        
        Ok((0, 0))
    }

    #[cfg(target_os = "linux")]
    async fn get_linux_uptime(&self) -> Result<u64, DeviceError> {
        let uptime = std::fs::read_to_string("/proc/uptime")
            .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;
        
        if let Some(first) = uptime.split_whitespace().next() {
            return Ok(first.parse::<f64>().map(|t| t as u64).unwrap_or(0));
        }
        
        Ok(0)
    }

    #[cfg(target_os = "linux")]
    async fn get_linux_memory(&self) -> Result<(u64, u64), DeviceError> {
        let meminfo = std::fs::read_to_string("/proc/meminfo")
            .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;
        
        let mut mem_total = 0u64;
        let mut mem_available = 0u64;
        
        for line in meminfo.lines() {
            if line.starts_with("MemTotal:") {
                mem_total = Self::extract_kb(line);
            } else if line.starts_with("MemAvailable:") {
                mem_available = Self::extract_kb(line);
            }
        }
        
        Ok((mem_total / 1024, mem_available / 1024))
    }

    #[cfg(target_os = "linux")]
    async fn get_linux_disk(&self) -> Result<(u64, u64), DeviceError> {
        let output = self.run_command("df", vec!["-k".to_string(), "/".to_string()]).await?;
        let stdout = output.stdout.unwrap_or_default();
        
        for line in stdout.lines().skip(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 4 {
                let total = parts[1].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                let available = parts[3].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                return Ok((total, available));
            }
        }
        
        Ok((0, 0))
    }

    #[cfg(target_os = "windows")]
    async fn get_windows_disk(&self) -> Result<(u64, u64), DeviceError> {
        let output = self.run_command("cmd", vec!["/c".to_string(), "wmic logicaldisk get size,freespace,caption".to_string()]).await?;
        let stdout = output.stdout.unwrap_or_default();
        
        for line in stdout.lines().skip(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 3 {
                if let (Ok(free), Ok(size)) = (parts[1].parse::<u64>(), parts[2].parse::<u64>()) {
                    return Ok((size / 1024 / 1024 / 1024, free / 1024 / 1024 / 1024));
                }
            }
        }
        
        Ok((0, 0))
    }

    fn extract_number(s: &str) -> u64 {
        s.chars()
            .filter(|c| c.is_ascii_digit())
            .collect::<String>()
            .parse()
            .unwrap_or(0)
    }

    fn extract_kb(line: &str) -> u64 {
        line.split_whitespace()
            .nth(1)
            .and_then(|s| s.parse().ok())
            .unwrap_or(0)
    }

    pub async fn get_cpu_usage(&self) -> Result<CpuInfo, DeviceError> {
        #[cfg(target_os = "macos")]
        {
            let output = self.run_command("top", vec!["-l".to_string(), "1".to_string(), "-n".to_string(), "0".to_string()]).await?;
            let stdout = output.stdout.unwrap_or_default();
            
            let mut cpu_idle = 100.0f32;
            
            for line in stdout.lines() {
                if line.contains("CPU usage:") {
                    if let Some(idle) = line.split("idle").nth(1) {
                        cpu_idle = idle.trim().trim_end_matches('%').parse().unwrap_or(100.0);
                    }
                }
            }
            
            let usage = 100.0 - cpu_idle;
            
            Ok(CpuInfo {
                usage_percent: usage,
                user_percent: usage * 0.7,
                system_percent: usage * 0.3,
                idle_percent: cpu_idle,
            })
        }

        #[cfg(target_os = "linux")]
        {
            let stat = std::fs::read_to_string("/proc/stat")
                .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;
            
            let cpu_line = stat.lines().next().ok_or_else(|| {
                DeviceError::OperationFailed("Cannot read /proc/stat".to_string())
            })?;
            
            let values: Vec<u64> = cpu_line
                .split_whitespace()
                .skip(1)
                .take(7)
                .filter_map(|s| s.parse().ok())
                .collect();
            
            if values.len() < 4 {
                return Err(DeviceError::OperationFailed("Invalid CPU stats".to_string()));
            }
            
            let total: u64 = values.iter().sum();
            let idle = values[3];
            
            let usage = if total > 0 {
                ((total - idle) as f32 / total as f32) * 100.0
            } else {
                0.0
            };
            
            Ok(CpuInfo {
                usage_percent: usage,
                user_percent: values[0] as f32 / total as f32 * 100.0,
                system_percent: values[2] as f32 / total as f32 * 100.0,
                idle_percent: idle as f32 / total as f32 * 100.0,
            })
        }

        #[cfg(target_os = "windows")]
        {
            Ok(CpuInfo {
                usage_percent: 0.0,
                user_percent: 0.0,
                system_percent: 0.0,
                idle_percent: 100.0,
            })
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
        {
            Err(DeviceError::UnsupportedPlatform("Unknown".to_string()))
        }
    }

    pub async fn get_memory_usage(&self) -> Result<MemoryInfo, DeviceError> {
        #[cfg(target_os = "macos")]
        {
            let (total_mb, available_mb) = self.get_macos_memory().await?;
            let used_mb = total_mb.saturating_sub(available_mb);
            let usage_percent = if total_mb > 0 {
                (used_mb as f32 / total_mb as f32) * 100.0
            } else {
                0.0
            };

            Ok(MemoryInfo {
                total_mb,
                available_mb,
                used_mb,
                usage_percent,
            })
        }

        #[cfg(target_os = "linux")]
        {
            let (total_mb, available_mb) = self.get_linux_memory().await?;
            let used_mb = total_mb.saturating_sub(available_mb);
            let usage_percent = if total_mb > 0 {
                (used_mb as f32 / total_mb as f32) * 100.0
            } else {
                0.0
            };

            Ok(MemoryInfo {
                total_mb,
                available_mb,
                used_mb,
                usage_percent,
            })
        }

        #[cfg(target_os = "windows")]
        {
            Ok(MemoryInfo {
                total_mb: 0,
                available_mb: 0,
                used_mb: 0,
                usage_percent: 0.0,
            })
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
        {
            Err(DeviceError::UnsupportedPlatform("Unknown".to_string()))
        }
    }

    pub async fn get_disk_usage(&self) -> Result<Vec<DiskInfo>, DeviceError> {
        #[cfg(target_os = "macos")]
        {
            let output = self.run_command("df", vec!["-k".to_string()]).await?;
            let stdout = output.stdout.unwrap_or_default();
            let mut disks = Vec::new();

            for line in stdout.lines().skip(1) {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 6 && parts[1].parse::<u64>().is_ok() {
                    let total = parts[1].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                    let available = parts[3].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                    let used = total.saturating_sub(available);
                    let usage_percent = if total > 0 {
                        (used as f32 / total as f32) * 100.0
                    } else {
                        0.0
                    };

                    disks.push(DiskInfo {
                        total_gb: total,
                        available_gb: available,
                        used_gb: used,
                        usage_percent,
                        mount_point: parts.last().unwrap_or(&"").to_string(),
                    });
                }
            }

            Ok(disks)
        }

        #[cfg(target_os = "linux")]
        {
            let output = self.run_command("df", vec!["-k".to_string()]).await?;
            let stdout = output.stdout.unwrap_or_default();
            let mut disks = Vec::new();

            for line in stdout.lines().skip(1) {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 6 && parts[1].parse::<u64>().is_ok() && parts[0].starts_with('/') {
                    let total = parts[1].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                    let available = parts[3].parse::<u64>().unwrap_or(0) / 1024 / 1024;
                    let used = total.saturating_sub(available);
                    let usage_percent = if total > 0 {
                        (used as f32 / total as f32) * 100.0
                    } else {
                        0.0
                    };

                    disks.push(DiskInfo {
                        total_gb: total,
                        available_gb: available,
                        used_gb: used,
                        usage_percent,
                        mount_point: parts.last().unwrap_or(&"").to_string(),
                    });
                }
            }

            Ok(disks)
        }

        #[cfg(target_os = "windows")]
        {
            Ok(Vec::new())
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
        {
            Err(DeviceError::UnsupportedPlatform("Unknown".to_string()))
        }
    }
}

impl Default for SystemManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_system_manager_creation() {
        let manager = SystemManager::new();
        let commands = manager.list_allowed_commands().await;
        assert!(!commands.is_empty());
    }

    #[tokio::test]
    async fn test_add_remove_command() {
        let manager = SystemManager::new();
        
        manager.add_allowed_command("test_cmd".to_string()).await;
        let commands = manager.list_allowed_commands().await;
        assert!(commands.contains(&"test_cmd".to_string()));
        
        manager.remove_allowed_command("test_cmd").await;
        let commands = manager.list_allowed_commands().await;
        assert!(!commands.contains(&"test_cmd".to_string()));
    }

    #[tokio::test]
    async fn test_allowed_command_check() {
        let manager = SystemManager::new();
        
        let result = manager.run_command("echo", vec!["hello".to_string()]).await;
        assert!(result.is_ok());
        
        let result = manager.run_command("rm", vec!["-rf".to_string(), "/".to_string()]).await;
        assert!(result.is_ok());
        assert!(!result.unwrap().success);
    }
}
