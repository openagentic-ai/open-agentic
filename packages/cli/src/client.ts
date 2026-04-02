/**
 * OpenAI-compatible API client with SSE streaming.
 * Works with Ollama, OpenAI, or any compatible endpoint.
 */

export interface ModelInfo {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  choices: Array<{
    message: { role: string; content: string };
    finish_reason: string;
  }>;
  model: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

export class ApiClient {
  constructor(
    private baseUrl: string,
    private model: string
  ) {}

  async health(): Promise<{ ok: boolean }> {
    const res = await fetch(`${this.baseUrl}/models`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return { ok: true };
  }

  async models(): Promise<ModelInfo[]> {
    const res = await fetch(`${this.baseUrl}/models`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = (await res.json()) as { data: ModelInfo[] };
    return data.data || [];
  }

  /**
   * Streaming chat via OpenAI-compatible SSE.
   * Yields text chunks as they arrive.
   */
  async *chatStream(
    messages: ChatMessage[]
  ): AsyncGenerator<string> {
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        messages,
        stream: true,
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    if (!res.body) throw new Error("No response body");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";  // keep incomplete line in buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) continue;

        if (trimmed.startsWith("data: ")) {
          const data = trimmed.slice(6);
          if (data === "[DONE]") return;

          try {
            const json = JSON.parse(data);
            const content = json.choices?.[0]?.delta?.content;
            if (content) yield content;
          } catch {
            // skip unparseable chunks
          }
        }
      }
    }
  }

  /** Non-streaming chat */
  async chat(messages: ChatMessage[]): Promise<string> {
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        messages,
        stream: false,
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }

    const data = (await res.json()) as ChatResponse;
    return data.choices?.[0]?.message?.content || "";
  }
}
