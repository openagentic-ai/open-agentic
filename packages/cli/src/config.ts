import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import { homedir } from "os";

export interface CliConfig {
  apiUrl: string;
  model: string;
  systemPrompt: string;
}

const CONFIG_DIR = join(homedir(), ".openagentic");
const CONFIG_FILE = join(CONFIG_DIR, "cli.json");

const DEFAULTS: CliConfig = {
  apiUrl: "http://localhost:11434/v1",
  model: "qwen3:14b",
  systemPrompt: "You are OpenAgentic AI assistant. Be helpful, concise, and accurate. Respond in the same language as the user.",
};

export function loadConfig(): CliConfig {
  try {
    if (existsSync(CONFIG_FILE)) {
      const raw = readFileSync(CONFIG_FILE, "utf-8");
      return { ...DEFAULTS, ...JSON.parse(raw) };
    }
  } catch {
    // ignore parse errors
  }
  return { ...DEFAULTS };
}

export function saveConfig(config: CliConfig): void {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2) + "\n");
}

export function getConfigPath(): string {
  return CONFIG_FILE;
}
