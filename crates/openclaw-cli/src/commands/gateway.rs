//! Gateway 命令

use anyhow::Result;
use openclaw_core::Config;
use openclaw_server::gateway_service::Gateway;
use openclaw_server::server_config::ServerConfig;
use std::path::PathBuf;

fn get_config_dir() -> Option<PathBuf> {
    dirs::home_dir().map(|p| p.join(".openclaw-rust"))
}

pub async fn run(
    port: u16,
    host: String,
    verbose: bool,
    agents: bool,
    channels: bool,
    voice: bool,
    canvas: bool,
) -> Result<()> {
    if verbose {
        tracing::info!("Verbose mode enabled");
    }

    let config = if let Some(config_dir) = get_config_dir() {
        tracing::info!("Loading configuration from: {:?}", config_dir);
        let mut config = ServerConfig::load_or_default(&config_dir);
        config.core.server.port = port;
        config.core.server.host = host;
        config.core.server.enable_agents = agents;
        config.core.server.enable_channels = channels;
        config.core.server.enable_voice = voice;
        config.core.server.enable_canvas = canvas;
        config
    } else {
        tracing::info!("Could not determine config directory, using CLI args only");
        let core = Config::default();
        let mut config = ServerConfig::from_core(core);
        config.core.server.port = port;
        config.core.server.host = host;
        config.core.server.enable_agents = agents;
        config.core.server.enable_channels = channels;
        config.core.server.enable_voice = voice;
        config.core.server.enable_canvas = canvas;
        config
    };

    tracing::info!("Starting OpenClaw Gateway...");
    tracing::info!("Configuration: {:?}", config.core.server);
    tracing::info!(
        "Services: agents={}, channels={}, voice={}, canvas={}",
        config.core.server.enable_agents,
        config.core.server.enable_channels,
        config.core.server.enable_voice,
        config.core.server.enable_canvas
    );
    if !config.agents.list.is_empty() {
        tracing::info!("Loaded {} agents from agents.yaml", config.agents.list.len());
    }
    if config.devices.enabled {
        tracing::info!("Devices enabled, loaded {} devices from devices.yaml", config.devices.nodes.len());
    }
    if !config.workspaces.workspaces.is_empty() {
        tracing::info!("Loaded {} workspaces from workspaces.yaml", config.workspaces.workspaces.len());
    }

    let gateway: openclaw_server::gateway_service::Gateway = Gateway::new(config).await?;
    gateway.start().await?;

    Ok(())
}
