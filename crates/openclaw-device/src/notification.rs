use crate::nodes::{DeviceError, NotificationResult};
use std::process::Command;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone)]
pub enum NotificationCategory {
    Message,
    Reminder,
    Alert,
    Info,
    Custom(String),
}

impl NotificationCategory {
    pub fn as_str(&self) -> &str {
        match self {
            NotificationCategory::Message => "message",
            NotificationCategory::Reminder => "reminder",
            NotificationCategory::Alert => "alert",
            NotificationCategory::Info => "info",
            NotificationCategory::Custom(s) => s.as_str(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct RichNotification {
    pub title: String,
    pub body: String,
    pub icon: Option<String>,
    pub sound: Option<String>,
    pub category: Option<NotificationCategory>,
    pub image_url: Option<String>,
    pub actions: Vec<NotificationAction>,
    pub urgency: NotificationUrgency,
    pub timeout: Option<u64>,
    pub persistent: bool,
}

#[derive(Debug, Clone)]
pub struct NotificationAction {
    pub id: String,
    pub label: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NotificationUrgency {
    Low,
    Normal,
    High,
    Critical,
}

impl Default for RichNotification {
    fn default() -> Self {
        Self {
            title: String::new(),
            body: String::new(),
            icon: None,
            sound: None,
            category: None,
            image_url: None,
            actions: Vec::new(),
            urgency: NotificationUrgency::Normal,
            timeout: None,
            persistent: false,
        }
    }
}

impl RichNotification {
    pub fn new(title: impl Into<String>, body: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            body: body.into(),
            ..Default::default()
        }
    }

    pub fn with_icon(mut self, icon: impl Into<String>) -> Self {
        self.icon = Some(icon.into());
        self
    }

    pub fn with_sound(mut self, sound: impl Into<String>) -> Self {
        self.sound = Some(sound.into());
        self
    }

    pub fn with_category(mut self, category: NotificationCategory) -> Self {
        self.category = Some(category);
        self
    }

    pub fn with_urgency(mut self, urgency: NotificationUrgency) -> Self {
        self.urgency = urgency;
        self
    }

    pub fn with_timeout(mut self, seconds: u64) -> Self {
        self.timeout = Some(seconds);
        self
    }

    pub fn with_persistent(mut self) -> Self {
        self.persistent = true;
        self
    }

    pub fn with_action(mut self, id: impl Into<String>, label: impl Into<String>) -> Self {
        self.actions.push(NotificationAction {
            id: id.into(),
            label: label.into(),
        });
        self
    }
}

pub struct NotificationManager {
    history: Arc<RwLock<Vec<NotificationHistoryEntry>>>,
    max_history: usize,
    default_sound: String,
}

#[derive(Debug, Clone)]
struct NotificationHistoryEntry {
    id: String,
    title: String,
    body: String,
    timestamp: i64,
    success: bool,
}

impl NotificationManager {
    pub fn new() -> Self {
        Self {
            history: Arc::new(RwLock::new(Vec::new())),
            max_history: 100,
            default_sound: "Glass".to_string(),
        }
    }

    pub fn with_max_history(mut self, max: usize) -> Self {
        self.max_history = max;
        self
    }

    pub fn with_default_sound(mut self, sound: impl Into<String>) -> Self {
        self.default_sound = sound.into();
        self
    }

    pub async fn send_notification(
        &self,
        title: &str,
        body: &str,
        icon: Option<&str>,
    ) -> Result<NotificationResult, DeviceError> {
        let rich = RichNotification::new(title, body)
            .with_icon(icon.unwrap_or("SF Symbols:bell.fill"));
        self.send_rich_notification(rich).await
    }

    pub async fn send_rich_notification(
        &self,
        rich: RichNotification,
    ) -> Result<NotificationResult, DeviceError> {
        let notification_id = uuid::Uuid::new_v4().to_string();
        let sound = rich.sound.as_deref().unwrap_or(&self.default_sound);

        #[cfg(target_os = "macos")]
        {
            let mut script = format!(
                r#"display notification "{}" with title "{}""#,
                rich.body, rich.title
            );

            if let Some(cat) = &rich.category {
                script.push_str(&format!(" subtitle \"{}\"", cat.as_str()));
            }

            script.push_str(&format!(" sound name \"{}\"", sound));

            let output = Command::new("osascript")
                .arg("-e")
                .arg(&script)
                .output()
                .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;

            let success = output.status.success();
            self.add_to_history(&notification_id, &rich.title, &rich.body, success)
                .await;

            if success {
                Ok(NotificationResult {
                    success: true,
                    notification_id: Some(notification_id),
                    error: None,
                })
            } else {
                let error = String::from_utf8_lossy(&output.stderr).to_string();
                Ok(NotificationResult {
                    success: false,
                    notification_id: None,
                    error: Some(error),
                })
            }
        }

        #[cfg(target_os = "linux")]
        {
            let mut args = vec![rich.title.as_str(), rich.body.as_str()];

            if let Some(icon) = &rich.icon {
                args.push("-i");
                args.push(icon);
            }

            if let Some(cat) = &rich.category {
                args.push("-u");
                args.push(match rich.urgency {
                    NotificationUrgency::Low => "low",
                    NotificationUrgency::Normal => "normal",
                    NotificationUrgency::Critical => "critical",
                });
                args.push("-A");
                args.push(&format!("category={}", cat.as_str()));
            }

            let output = Command::new("notify-send")
                .args(&args)
                .output()
                .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;

            let success = output.status.success();
            self.add_to_history(&notification_id, &rich.title, &rich.body, success)
                .await;

            if success {
                Ok(NotificationResult {
                    success: true,
                    notification_id: Some(notification_id),
                    error: None,
                })
            } else {
                Ok(NotificationResult {
                    success: false,
                    notification_id: None,
                    error: Some("notify-send failed".to_string()),
                })
            }
        }

        #[cfg(target_os = "windows")]
        {
            let ps_script = format!(
                r#"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); $text = $xml.GetElementsByTagName("text"); $text[0].AppendChild($xml.CreateTextNode("{}")) | Out-Null; $text[1].AppendChild($xml.CreateTextNode("{}")) | Out-Null; $toast = [Windows.UI.Notifications.ToastNotification]::new($xml); [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OpenClaw").Show($toast)"#,
                rich.title.replace("\"", "'"),
                rich.body.replace("\"", "'")
            );

            let output = Command::new("powershell")
                .args(["-NoProfile", "-Command", &ps_script])
                .output()
                .map_err(|e| DeviceError::OperationFailed(e.to_string()))?;

            let success = output.status.success();
            self.add_to_history(&notification_id, &rich.title, &rich.body, success)
                .await;

            if success {
                Ok(NotificationResult {
                    success: true,
                    notification_id: Some(notification_id),
                    error: None,
                })
            } else {
                Ok(NotificationResult {
                    success: false,
                    notification_id: None,
                    error: Some("Windows toast notification failed".to_string()),
                })
            }
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
        {
            Ok(NotificationResult {
                success: false,
                notification_id: None,
                error: Some("不支持的平台".to_string()),
            })
        }
    }

    pub async fn send_system_notification(
        &self,
        title: &str,
        message: &str,
    ) -> Result<NotificationResult, DeviceError> {
        self.send_notification(title, message, None).await
    }

    pub async fn send_category_notification(
        &self,
        title: &str,
        body: &str,
        category: NotificationCategory,
    ) -> Result<NotificationResult, DeviceError> {
        let rich = RichNotification::new(title, body).with_category(category);
        self.send_rich_notification(rich).await
    }

    pub async fn send_urgent_notification(
        &self,
        title: &str,
        body: &str,
    ) -> Result<NotificationResult, DeviceError> {
        let rich = RichNotification::new(title, body)
            .with_urgency(NotificationUrgency::Critical)
            .with_sound("Basso");
        self.send_rich_notification(rich).await
    }

    async fn add_to_history(&self, id: &str, title: &str, body: &str, success: bool) {
        let mut history = self.history.write().await;
        history.push(NotificationHistoryEntry {
            id: id.to_string(),
            title: title.to_string(),
            body: body.to_string(),
            timestamp: chrono::Utc::now().timestamp(),
            success,
        });

        if history.len() > self.max_history {
            history.remove(0);
        }
    }

    pub async fn get_history(&self, limit: Option<usize>) -> Vec<NotificationHistoryEntry> {
        let history = self.history.read().await;
        let limit = limit.unwrap_or(self.max_history);
        history.iter().rev().take(limit).cloned().collect()
    }

    pub async fn clear_history(&self) {
        let mut history = self.history.write().await;
        history.clear();
    }

    pub async fn get_history_count(&self) -> usize {
        self.history.read().await.len()
    }
}

impl Default for NotificationManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rich_notification_builder() {
        let rich = RichNotification::new("Test Title", "Test Body")
            .with_icon("icon.png")
            .with_sound("ping")
            .with_category(NotificationCategory::Message)
            .with_urgency(NotificationUrgency::High)
            .with_timeout(10)
            .with_action("view", "查看");

        assert_eq!(rich.title, "Test Title");
        assert_eq!(rich.body, "Test Body");
        assert!(rich.icon.is_some());
        assert!(rich.sound.is_some());
        assert!(rich.category.is_some());
    }

    #[test]
    fn test_notification_category() {
        assert_eq!(NotificationCategory::Message.as_str(), "message");
        assert_eq!(NotificationCategory::Custom("custom".to_string()).as_str(), "custom");
    }

    #[tokio::test]
    async fn test_notification_manager_creation() {
        let manager = NotificationManager::new();
        assert_eq!(manager.get_history_count().await, 0);
    }

    #[tokio::test]
    async fn test_notification_history() {
        let manager = NotificationManager::new();
        
        manager.add_to_history("test-1", "Title 1", "Body 1", true).await;
        manager.add_to_history("test-2", "Title 2", "Body 2", false).await;
        
        assert_eq!(manager.get_history_count().await, 2);
        
        let history = manager.get_history(Some(1)).await;
        assert_eq!(history.len(), 1);
    }

    #[tokio::test]
    async fn test_clear_history() {
        let manager = NotificationManager::new();
        
        manager.add_to_history("test-1", "Title", "Body", true).await;
        assert_eq!(manager.get_history_count().await, 1);
        
        manager.clear_history().await;
        assert_eq!(manager.get_history_count().await, 0);
    }
}
