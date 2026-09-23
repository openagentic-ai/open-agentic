"""启动本地优先个人助手验证原型。

默认连接 127.0.0.1:11434 的 OpenAI 兼容本地服务；通过环境变量可切换到用户自己的 API。

    /opt/open-agentic/.venv/bin/python scripts/run_personal_demo.py

云端模式示例：
    PERSONAL_MODEL_MODE=api PERSONAL_MODEL=openai/gpt-4o \
    PERSONAL_API_BASE=https://api.openai.com/v1 PERSONAL_API_KEY=... \
    /opt/open-agentic/.venv/bin/python scripts/run_personal_demo.py
"""
from extensions.personal_demo.app import main


if __name__ == "__main__":
    main()
