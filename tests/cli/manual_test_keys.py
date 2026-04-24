"""Interactive test for read_nav_key — run in a real terminal."""
import sys
sys.path.insert(0, "src")

from openagentic.cli.platform_adapter import CLI_PLATFORM

print("=== read_nav_key 交互测试 ===")
print("请依次测试: ↑ ↓ ← → Enter q Ctrl-C")
print("每次按键后会显示识别结果，按 q 或 Ctrl-C 退出")
print("-" * 40)

while True:
    sys.stdout.write("按任意键> ")
    sys.stdout.flush()
    key = CLI_PLATFORM.read_nav_key()
    print(f"  识别为: {key!r}")
    if key in ("quit", "interrupt"):
        print("退出测试")
        break
