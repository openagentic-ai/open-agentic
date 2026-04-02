#!/usr/bin/env node

import { Command } from "commander";
import { loadConfig, saveConfig, getConfigPath } from "./config.js";
import { ApiClient } from "./client.js";
import { banner, formatError, formatSuccess, style } from "./utils.js";
import { startRepl } from "./repl.js";

const VERSION = "0.1.0";

const program = new Command()
  .name("oa")
  .description("OpenAgentic CLI - interactive AI assistant")
  .version(VERSION)
  .option("--api <url>", "API base URL override")
  .option("-p, --prompt <text>", "Non-interactive: send prompt and exit")
  .option("-m, --model <name>", "Model override");

// Default: REPL or one-shot
program.action(async (opts) => {
  const config = loadConfig();
  if (opts.api) config.apiUrl = opts.api;
  if (opts.model) config.model = opts.model;

  // Non-interactive: -p "prompt"
  if (opts.prompt) {
    const client = new ApiClient(config.apiUrl, config.model);
    try {
      const messages = [
        { role: "system" as const, content: config.systemPrompt },
        { role: "user" as const, content: opts.prompt },
      ];
      for await (const chunk of client.chatStream(messages)) {
        process.stdout.write(chunk);
      }
      process.stdout.write("\n");
    } catch {
      // Fallback to non-streaming
      try {
        const client2 = new ApiClient(config.apiUrl, config.model);
        const reply = await client2.chat([
          { role: "system", content: config.systemPrompt },
          { role: "user", content: opts.prompt },
        ]);
        console.log(reply);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(formatError(msg));
        process.exit(1);
      }
    }
    return;
  }

  // Interactive REPL
  console.log(banner(VERSION));
  await startRepl(config);
});

// oa status
program
  .command("status")
  .description("Check API connectivity")
  .action(async () => {
    const config = loadConfig();
    const opts = program.opts();
    if (opts.api) config.apiUrl = opts.api;

    const client = new ApiClient(config.apiUrl, config.model);
    try {
      await client.health();
      const models = await client.models();
      console.log(formatSuccess(`API: ${config.apiUrl}`));
      console.log(`  Models: ${models.length} available`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(formatError(`Cannot connect: ${msg}`));
      process.exit(1);
    }
  });

// oa models
program
  .command("models")
  .description("List available models")
  .action(async () => {
    const config = loadConfig();
    const opts = program.opts();
    if (opts.api) config.apiUrl = opts.api;

    const client = new ApiClient(config.apiUrl, config.model);
    try {
      const models = await client.models();
      if (models.length === 0) {
        console.log(style.dim("No models available."));
        return;
      }
      for (const m of models) {
        const marker = m.id === config.model ? style.success("● ") : "  ";
        console.log(`${marker}${m.id}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(formatError(msg));
      process.exit(1);
    }
  });

// oa config [set key value]
const configCmd = program
  .command("config")
  .description("View or set CLI configuration");

configCmd.action(() => {
  const config = loadConfig();
  console.log(style.bold("Configuration") + style.dim(` (${getConfigPath()})\n`));
  for (const [key, value] of Object.entries(config)) {
    const display = key === "systemPrompt"
      ? (value as string).slice(0, 60) + "..."
      : value || style.dim("(default)");
    console.log(`  ${style.info(key.padEnd(16))} ${display}`);
  }
});

configCmd
  .command("set <key> <value>")
  .description("Set a config value")
  .action((key: string, value: string) => {
    const config = loadConfig();
    if (!(key in config)) {
      console.error(formatError(`Unknown key: ${key}. Valid: ${Object.keys(config).join(", ")}`));
      process.exit(1);
    }
    (config as unknown as Record<string, string>)[key] = value;
    saveConfig(config);
    console.log(formatSuccess(`${key} = ${value}`));
  });

program.parse();
