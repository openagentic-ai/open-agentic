//! 流式语音识别模块

use std::sync::Arc;
use async_trait::async_trait;
use tokio::sync::mpsc;
use openclaw_core::{OpenClawError, Result};
use crate::types::{SttProvider, TranscriptionResult};

use super::SpeechToText;

#[derive(Debug, Clone)]
pub struct StreamingTranscriptionConfig {
    pub sample_rate: u32,
    pub channels: u16,
    pub buffer_size_ms: u32,
    pub language: Option<String>,
}

impl Default for StreamingTranscriptionConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000,
            channels: 1,
            buffer_size_ms: 100,
            language: None,
        }
    }
}

pub trait StreamingSpeechToText: Send + Sync {
    fn start_streaming(&self) -> StreamingHandle;
    
    fn config(&self) -> &StreamingTranscriptionConfig;
}

pub struct StreamingHandle {
    pub audio_tx: mpsc::Sender<StreamingAudioChunk>,
    pub result_rx: mpsc::Receiver<StreamingTranscriptionResult>,
}

#[derive(Debug, Clone)]
pub struct StreamingAudioChunk {
    pub data: Vec<u8>,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone)]
pub struct StreamingTranscriptionResult {
    pub text: String,
    pub is_final: bool,
    pub confidence: Option<f32>,
    pub start_ms: u64,
    pub end_ms: u64,
}

pub struct WhisperStreamingStt {
    config: StreamingTranscriptionConfig,
}

impl WhisperStreamingStt {
    pub fn new(config: StreamingTranscriptionConfig) -> Self {
        Self { config }
    }

    pub fn with_default_config() -> Self {
        Self::new(StreamingTranscriptionConfig::default())
    }
}

impl StreamingSpeechToText for WhisperStreamingStt {
    fn start_streaming(&self) -> StreamingHandle {
        let (audio_tx, _audio_rx) = mpsc::channel(100);
        let (result_tx, result_rx) = mpsc::channel(100);
        
        StreamingHandle {
            audio_tx,
            result_rx,
        }
    }

    fn config(&self) -> &StreamingTranscriptionConfig {
        &self.config
    }
}

pub struct WhisperStreamingBuilder {
    config: StreamingTranscriptionConfig,
}

impl WhisperStreamingBuilder {
    pub fn new() -> Self {
        Self {
            config: StreamingTranscriptionConfig::default(),
        }
    }

    pub fn sample_rate(mut self, rate: u32) -> Self {
        self.config.sample_rate = rate;
        self
    }

    pub fn channels(mut self, channels: u16) -> Self {
        self.config.channels = channels;
        self
    }

    pub fn buffer_size_ms(mut self, size: u32) -> Self {
        self.config.buffer_size_ms = size;
        self
    }

    pub fn language(mut self, language: &str) -> Self {
        self.config.language = Some(language.to_string());
        self
    }

    pub fn build(self) -> WhisperStreamingStt {
        WhisperStreamingStt::new(self.config)
    }
}

impl Default for WhisperStreamingBuilder {
    fn default() -> Self {
        Self::new()
    }
}

pub struct AzureStreamingStt {
    config: StreamingTranscriptionConfig,
    api_key: String,
    region: String,
}

impl AzureStreamingStt {
    pub fn new(config: StreamingTranscriptionConfig, api_key: String, region: String) -> Self {
        Self { config, api_key, region }
    }
}

impl StreamingSpeechToText for AzureStreamingStt {
    fn start_streaming(&self) -> StreamingHandle {
        let (audio_tx, _audio_rx) = mpsc::channel(100);
        let (result_tx, result_rx) = mpsc::channel(100);
        
        StreamingHandle {
            audio_tx,
            result_rx,
        }
    }

    fn config(&self) -> &StreamingTranscriptionConfig {
        &self.config
    }
}

pub enum StreamingSttBackend {
    Whisper(WhisperStreamingStt),
    Azure(String, String),
}

impl StreamingSttBackend {
    pub fn new_whisper() -> Self {
        Self::Whisper(WhisperStreamingStt::with_default_config())
    }

    pub fn new_azure(api_key: &str, region: &str) -> Self {
        Self::Azure(api_key.to_string(), region.to_string())
    }

    pub fn start_streaming(&self) -> StreamingHandle {
        match self {
            Self::Whisper(stt) => stt.start_streaming(),
            Self::Azure(_, _) => {
                let (audio_tx, _) = mpsc::channel(100);
                let (result_tx, result_rx) = mpsc::channel(100);
                StreamingHandle { audio_tx, result_rx }
            }
        }
    }
}

pub struct StreamingSttProcessor {
    backend: StreamingSttBackend,
    is_running: Arc<std::sync::atomic::AtomicBool>,
}

impl StreamingSttProcessor {
    pub fn new(backend: StreamingSttBackend) -> Self {
        Self {
            backend,
            is_running: Arc::new(std::sync::atomic::AtomicBool::new(false)),
        }
    }

    pub fn start(&self) -> StreamingHandle {
        self.is_running.store(true, std::sync::atomic::Ordering::SeqCst);
        self.backend.start_streaming()
    }

    pub fn stop(&self) {
        self.is_running.store(false, std::sync::atomic::Ordering::SeqCst);
    }

    pub fn is_running(&self) -> bool {
        self.is_running.load(std::sync::atomic::Ordering::SeqCst)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_streaming_transcription_config_default() {
        let config = StreamingTranscriptionConfig::default();
        assert_eq!(config.sample_rate, 16000);
        assert_eq!(config.channels, 1);
        assert_eq!(config.buffer_size_ms, 100);
    }

    #[test]
    fn test_whisper_streaming_builder() {
        let stt = WhisperStreamingBuilder::new()
            .sample_rate(48000)
            .channels(2)
            .buffer_size_ms(50)
            .language("en")
            .build();
        
        let config = stt.config();
        assert_eq!(config.sample_rate, 48000);
        assert_eq!(config.channels, 2);
        assert_eq!(config.buffer_size_ms, 50);
        assert_eq!(config.language.as_deref(), Some("en"));
    }

    #[test]
    fn test_streaming_stt_processor() {
        let backend = StreamingSttBackend::new_whisper();
        let processor = StreamingSttProcessor::new(backend);
        
        assert!(!processor.is_running());
        
        let _handle = processor.start();
        assert!(processor.is_running());
        
        processor.stop();
        assert!(!processor.is_running());
    }
}
