//! 本地 Whisper 模型支持
//!
//! 使用 whisper.cpp 实现本地语音识别

use async_trait::async_trait;
use openclaw_core::{OpenClawError, Result};

#[cfg(feature = "local-whisper")]
use whisper_rs::{FullParams, WhisperContext};

use crate::types::{SttProvider, TranscriptionResult};

/// 本地 Whisper 配置
#[derive(Debug, Clone)]
pub struct LocalWhisperConfig {
    /// 模型文件路径
    pub model_path: String,
    /// 语言 (可选，自动检测)
    pub language: Option<String>,
    /// 是否翻译为英文
    pub translate: bool,
    /// 线程数
    pub n_threads: i32,
}

impl Default for LocalWhisperConfig {
    fn default() -> Self {
        Self {
            model_path: String::new(),
            language: None,
            translate: false,
            n_threads: 4,
        }
    }
}

/// 本地 Whisper STT
pub struct LocalWhisperStt {
    config: LocalWhisperConfig,
    #[cfg(feature = "local-whisper")]
    context: Option<WhisperContext>,
}

impl LocalWhisperStt {
    pub fn new(config: LocalWhisperConfig) -> Self {
        Self {
            config,
            #[cfg(feature = "local-whisper")]
            context: None,
        }
    }

    /// 从模型路径加载模型
    #[cfg(feature = "local-whisper")]
    pub fn load_model(&mut self) -> Result<()> {
        self.check_model()?;
        
        let context = WhisperContext::new(&self.config.model_path)
            .map_err(|e| OpenClawError::Config(format!("加载 Whisper 模型失败: {}", e)))?;
        
        self.context = Some(context);
        Ok(())
    }

    #[cfg(not(feature = "local-whisper"))]
    pub fn load_model(&self) -> Result<()> {
        self.check_model()
    }

    /// 检查模型文件是否存在
    pub fn check_model(&self) -> Result<()> {
        let path = std::path::Path::new(&self.config.model_path);
        if !path.exists() {
            return Err(OpenClawError::Config(format!(
                "Whisper 模型文件不存在: {}",
                self.config.model_path
            )));
        }
        Ok(())
    }

    /// 下载模型
    pub async fn download_model(model_type: WhisperModelType) -> Result<String> {
        let models_dir = Self::get_models_dir()?;

        let (filename, url) = match model_type {
            WhisperModelType::Tiny => (
                "ggml-tiny.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
            ),
            WhisperModelType::TinyEn => (
                "ggml-tiny.en.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin",
            ),
            WhisperModelType::Base => (
                "ggml-base.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            ),
            WhisperModelType::BaseEn => (
                "ggml-base.en.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
            ),
            WhisperModelType::Small => (
                "ggml-small.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
            ),
            WhisperModelType::Medium => (
                "ggml-medium.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
            ),
            WhisperModelType::Large => (
                "ggml-large-v3.bin",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
            ),
        };

        let model_path = models_dir.join(filename);

        if model_path.exists() {
            println!("✅ 模型已存在: {}", model_path.display());
            return Ok(model_path.to_string_lossy().to_string());
        }

        println!("📥 下载 Whisper 模型: {}", filename);
        println!("   URL: {}", url);

        // 创建目录
        std::fs::create_dir_all(&models_dir)
            .map_err(|e| OpenClawError::Config(format!("创建模型目录失败: {}", e)))?;

        // 下载
        let response = reqwest::get(url)
            .await
            .map_err(|e| OpenClawError::Http(format!("下载模型失败: {}", e)))?;

        if !response.status().is_success() {
            return Err(OpenClawError::Http(format!(
                "下载模型失败: HTTP {}",
                response.status()
            )));
        }

        let bytes = response
            .bytes()
            .await
            .map_err(|e| OpenClawError::Http(format!("读取模型数据失败: {}", e)))?;

        std::fs::write(&model_path, &bytes)
            .map_err(|e| OpenClawError::Config(format!("保存模型失败: {}", e)))?;

        println!("✅ 模型已保存到: {}", model_path.display());

        Ok(model_path.to_string_lossy().to_string())
    }

    /// 获取模型目录
    fn get_models_dir() -> Result<std::path::PathBuf> {
        let home = std::env::var("HOME")
            .or_else(|_| std::env::var("USERPROFILE"))
            .unwrap_or_else(|_| ".".to_string());
        Ok(std::path::PathBuf::from(home)
            .join(".openclaw-rust")
            .join("models"))
    }

    /// 列出可用模型
    pub fn list_available_models() -> Vec<WhisperModelInfo> {
        vec![
            WhisperModelInfo {
                name: "tiny".to_string(),
                size_mb: 75,
                languages: 99,
                recommended: false,
                description: "最小模型，速度快但准确度较低".to_string(),
            },
            WhisperModelInfo {
                name: "tiny.en".to_string(),
                size_mb: 75,
                languages: 1,
                recommended: false,
                description: "仅英语，速度最快".to_string(),
            },
            WhisperModelInfo {
                name: "base".to_string(),
                size_mb: 142,
                languages: 99,
                recommended: true,
                description: "基础模型，平衡速度和准确度".to_string(),
            },
            WhisperModelInfo {
                name: "base.en".to_string(),
                size_mb: 142,
                languages: 1,
                recommended: false,
                description: "仅英语，准确度较好".to_string(),
            },
            WhisperModelInfo {
                name: "small".to_string(),
                size_mb: 466,
                languages: 99,
                recommended: true,
                description: "小型模型，准确度较好".to_string(),
            },
            WhisperModelInfo {
                name: "medium".to_string(),
                size_mb: 1500,
                languages: 99,
                recommended: false,
                description: "中型模型，准确度高".to_string(),
            },
            WhisperModelInfo {
                name: "large-v3".to_string(),
                size_mb: 2900,
                languages: 99,
                recommended: false,
                description: "最大模型，准确度最高".to_string(),
            },
        ]
    }
}

#[async_trait]
impl super::SpeechToText for LocalWhisperStt {
    fn provider(&self) -> SttProvider {
        SttProvider::LocalWhisper
    }

    async fn transcribe(
        &self,
        audio_data: &[u8],
        language: Option<&str>,
    ) -> Result<TranscriptionResult> {
        #[cfg(feature = "local-whisper")]
        {
            use std::sync::Mutex;
            
            // 需要 Mutex 来获取 context 的可变引用
            // 由于 async_trait，不能直接用 RefCell，所以用全局锁
            static CONTEXT_MUTEX: std::sync::Mutex<Option<WhisperContext>> = std::sync::Mutex::new(None);
            
            // 先检查模型
            self.check_model()?;
            
            // 懒加载模型
            let mut ctx_guard = CONTEXT_MUTEX.lock().unwrap();
            if ctx_guard.is_none() {
                let ctx = WhisperContext::new(&self.config.model_path)
                    .map_err(|e| OpenClawError::Config(format!("加载模型失败: {}", e)))?;
                *ctx_guard = Some(ctx);
            }
            
            let context = ctx_guard.as_ref().unwrap();
            
            // 设置语言参数
            let mut params = FullParams::new();
            params.set_language(language);
            params.set_translate(self.config.translate);
            params.set_n_threads(self.config.n_threads);
            
            // 准备音频数据 (假设是 16kHz 16bit mono)
            let sample_rate = 16000u32;
            let samples: Vec<f32> = audio_data
                .chunks_exact(2)
                .map(|chunk| {
                    let sample = i16::from_le_bytes([chunk[0], chunk[1]]);
                    sample as f32 / 32768.0
                })
                .collect();
            
            // 执行转写
            let mut state = context
                .create_state()
                .map_err(|e| OpenClawError::Config(format!("创建状态失败: {}", e)))?;
            
            state
                .full(params, &samples)
                .map_err(|e| OpenClawError::Config(format!("转写失败: {}", e)))?;
            
            let num_segments = state
                .full_n_segments()
                .map_err(|e| OpenClawError::Config(format!("获取段落数失败: {}", e)))?;
            
            let mut full_text = String::new();
            for i in 0..num_segments {
                if let Ok(text) = state.full_get_segment_text(i) {
                    if !full_text.is_empty() {
                        full_text.push(' ');
                    }
                    full_text.push_str(&text);
                }
            }
            
            Ok(TranscriptionResult {
                text: full_text,
                language: language.map(String::from),
                duration: Some((samples.len() as f64) / (sample_rate as f64)),
                confidence: None,
            })
        }
        
        #[cfg(not(feature = "local-whisper"))]
        {
            let _ = (audio_data, language);
            self.check_model()?;
            Err(OpenClawError::Config(
                "本地 Whisper 需要启用 local-whisper feature。请使用 cargo build --features local-whisper 或安装 whisper-rs 依赖"
                    .to_string(),
            ))
        }
    }

    async fn is_available(&self) -> bool {
        self.check_model().is_ok()
    }
}

/// Whisper 模型类型
#[derive(Debug, Clone, Copy)]
pub enum WhisperModelType {
    Tiny,
    TinyEn,
    Base,
    BaseEn,
    Small,
    Medium,
    Large,
}

/// 模型信息
#[derive(Debug, Clone)]
pub struct WhisperModelInfo {
    pub name: String,
    pub size_mb: u64,
    pub languages: u32,
    pub recommended: bool,
    pub description: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_list_models() {
        let models = LocalWhisperStt::list_available_models();
        assert!(!models.is_empty());

        let recommended: Vec<_> = models.iter().filter(|m| m.recommended).collect();
        assert!(!recommended.is_empty());
    }

    #[test]
    fn test_default_config() {
        let config = LocalWhisperConfig::default();
        assert_eq!(config.n_threads, 4);
        assert!(!config.translate);
    }
}
