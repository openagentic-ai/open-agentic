"""Interactive test for the full selection menu — run in a real terminal."""
import sys
sys.path.insert(0, "src")

from openagentic.cli.platform_adapter import CLI_PLATFORM

items = ["OpenAI", "Anthropic", "DeepSeek", "Qwen", "Ollama"]
selected = 0

print("=== 模拟 provider 选择菜单 ===")
print("↑/↓ 选择，Enter 确认，q 取消")
print()

while True:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print("选择模型厂商（↑/↓ 选择，Enter 确认，q 取消）：")
    for i, item in enumerate(items):
        cursor = ">" if i == selected else " "
        print(f"  {cursor} {item}")

    key = CLI_PLATFORM.read_nav_key()
    if key == "up":
        selected = (selected - 1) % len(items)
    elif key == "down":
        selected = (selected + 1) % len(items)
    elif key == "enter":
        CLI_PLATFORM.drain_stdin_buffer(settle_ms=120)
        print(f"\n✓ 已选择: {items[selected]}")
        break
    elif key in ("quit", "interrupt"):
        CLI_PLATFORM.drain_stdin_buffer(settle_ms=120)
        print("\n✗ 已取消")
        break

print("\n--- 测试选择后的输入功能 ---")
CLI_PLATFORM.ensure_line_input_mode()
CLI_PLATFORM.drain_stdin_buffer(settle_ms=80)
try:
    user_input = input("请输入任意文字验证输入正常> ")
    print(f"你输入了: {user_input!r}")
    print("✓ 输入功能正常")
except (EOFError, KeyboardInterrupt):
    print("\n输入被中断")
