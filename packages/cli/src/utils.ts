import chalk from "chalk";

export const style = {
  brand: chalk.cyan.bold,
  success: chalk.green,
  error: chalk.red,
  warn: chalk.yellow,
  dim: chalk.gray,
  bold: chalk.bold,
  user: chalk.green.bold,
  assistant: chalk.cyan,
  info: chalk.blue,
};

export function banner(version: string): string {
  return [
    "",
    style.brand("  OpenAgentic CLI") + style.dim(` v${version}`),
    "",
  ].join("\n");
}

export function formatError(msg: string): string {
  return style.error("✗ ") + msg;
}

export function formatSuccess(msg: string): string {
  return style.success("✓ ") + msg;
}
