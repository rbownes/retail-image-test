import type { PipelineEvent } from "./types";

export function openEventStream(
  url: string,
  onEvent: (e: PipelineEvent) => void,
  onTerminal?: () => void,
  onError?: (err: Event) => void,
): () => void {
  const es = new EventSource(url);

  es.onmessage = (msg) => {
    try {
      const parsed = JSON.parse(msg.data) as PipelineEvent;
      onEvent(parsed);
    } catch (err) {
      console.error("failed to parse SSE message", err, msg.data);
    }
  };

  es.addEventListener("terminal", () => {
    onTerminal?.();
    es.close();
  });

  es.onerror = (err) => {
    onError?.(err);
    // EventSource auto-reconnects on transient errors; close on real failure.
    if (es.readyState === EventSource.CLOSED) {
      onTerminal?.();
    }
  };

  return () => {
    es.close();
  };
}
