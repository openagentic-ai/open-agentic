"""OpenAgentic CLI — lightweight chat REPL via Ollama."""

import asyncio
import sys

import litellm

litellm.drop_params = True

DEFAULT_MODEL = "ollama/qwen3:14b"
OLLAMA_BASE = "http://localhost:11434"


async def chat_loop(model: str, system_prompt: str | None = None):
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    print(f"OpenAgentic CLI  |  model: {model}")
    print("Type your message. Commands: /clear /model <name> /system <prompt> /quit")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input == "/quit":
            print("Bye!")
            break
        if user_input == "/clear":
            messages = [m for m in messages if m["role"] == "system"]
            print("[history cleared]")
            continue
        if user_input.startswith("/model "):
            model = user_input[7:].strip()
            print(f"[model → {model}]")
            continue
        if user_input.startswith("/system "):
            sp = user_input[8:].strip()
            messages = [m for m in messages if m["role"] != "system"]
            if sp:
                messages.insert(0, {"role": "system", "content": sp})
            print(f"[system prompt set]")
            continue

        messages.append({"role": "user", "content": user_input})

        # Determine api_base
        api_base = OLLAMA_BASE if model.startswith("ollama/") else None

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                stream=True,
                api_base=api_base,
            )
            full = ""
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    print(delta.content, end="", flush=True)
                    full += delta.content
            print()  # newline after stream
            messages.append({"role": "assistant", "content": full})
        except Exception as e:
            print(f"\n[ERROR] {e}")
            messages.pop()  # remove failed user message


def main():
    import argparse

    parser = argparse.ArgumentParser(description="OpenAgentic CLI Chat")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="LLM model (default: ollama/qwen3:14b)")
    parser.add_argument("-s", "--system", default=None, help="System prompt")
    args = parser.parse_args()

    asyncio.run(chat_loop(args.model, args.system))


if __name__ == "__main__":
    main()
