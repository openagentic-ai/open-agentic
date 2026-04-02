import * as readline from "readline";
import { ApiClient, type ChatMessage } from "./client.js";
import { style, formatError, formatSuccess } from "./utils.js";
import type { CliConfig } from "./config.js";

const SLASH_COMMANDS: Record<string, string> = {
  "/help": "Show this help message",
  "/clear": "Clear conversation history",
  "/model": "Show or switch model (/model <name>)",
  "/models": "List available models",
  "/status": "Check API connectivity",
  "/quit": "Exit",
};

export async function startRepl(config: CliConfig): Promise<void> {
  const client = new ApiClient(config.apiUrl, config.model);

  // Check connectivity
  try {
    await client.health();
    console.log(formatSuccess(`API: ${config.apiUrl}`));
    console.log(style.dim(`  Model: ${config.model}`));
  } catch {
    console.log(formatError(`Cannot connect to ${config.apiUrl}`));
    console.log(style.dim("  Is Ollama running? Try: ollama serve"));
    process.exit(1);
  }

  console.log(style.dim("\n  Type /help for commands, Ctrl+C to exit.\n"));

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: style.user("> "),
  });

  const history: ChatMessage[] = [
    { role: "system", content: config.systemPrompt },
  ];
  let currentModel = config.model;

  rl.prompt();

  rl.on("line", async (line: string) => {
    const input = line.trim();
    if (!input) {
      rl.prompt();
      return;
    }

    // Slash commands
    if (input.startsWith("/")) {
      await handleSlash(input, client, rl, currentModel, history, (m) => {
        currentModel = m;
      });
      rl.prompt();
      return;
    }

    // Chat
    history.push({ role: "user", content: input });

    try {
      process.stdout.write("\n");
      let full = "";

      const streamClient = new ApiClient(config.apiUrl, currentModel);
      for await (const chunk of streamClient.chatStream(history)) {
        process.stdout.write(chunk);
        full += chunk;
      }

      if (!full.endsWith("\n")) process.stdout.write("\n");
      process.stdout.write("\n");

      history.push({ role: "assistant", content: full });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.log("\n" + formatError(msg) + "\n");
    }

    rl.prompt();
  });

  rl.on("close", () => {
    console.log(style.dim("\nBye!"));
    process.exit(0);
  });
}

async function handleSlash(
  input: string,
  client: ApiClient,
  rl: readline.Interface,
  currentModel: string,
  history: ChatMessage[],
  setModel: (m: string) => void
): Promise<void> {
  const parts = input.split(/\s+/);
  const cmd = parts[0]!.toLowerCase();

  switch (cmd) {
    case "/help":
      console.log(style.bold("\n  Commands:"));
      for (const [name, desc] of Object.entries(SLASH_COMMANDS)) {
        console.log(`  ${style.info(name.padEnd(12))} ${desc}`);
      }
      console.log();
      break;

    case "/clear":
      history.length = 1; // keep system prompt
      console.log(formatSuccess("Conversation cleared.\n"));
      break;

    case "/model":
      if (parts[1]) {
        setModel(parts[1]);
        console.log(formatSuccess(`Switched to model: ${parts[1]}\n`));
      } else {
        console.log(style.dim(`\n  Current model: ${currentModel}\n`));
      }
      break;

    case "/models":
      try {
        const models = await client.models();
        if (models.length === 0) {
          console.log(style.dim("\n  No models available.\n"));
        } else {
          console.log(style.bold("\n  Available models:"));
          for (const m of models) {
            const marker = m.id === currentModel ? style.success(" ●") : "  ";
            console.log(`${marker} ${style.info(m.id)}`);
          }
          console.log();
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.log("\n" + formatError(msg) + "\n");
      }
      break;

    case "/status":
      try {
        await client.health();
        console.log("\n" + formatSuccess("API is reachable.\n"));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.log("\n" + formatError(msg) + "\n");
      }
      break;

    case "/quit":
    case "/exit":
    case "/q":
      rl.close();
      break;

    default:
      console.log(style.warn(`\n  Unknown: ${cmd}. Type /help\n`));
  }
}
