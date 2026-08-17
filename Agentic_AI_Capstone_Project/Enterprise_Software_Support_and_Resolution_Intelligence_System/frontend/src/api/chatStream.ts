// POST /chat/stream (A6) is Server-Sent Events over a POST body — browsers'
// native EventSource only supports GET and can't carry a custom
// Authorization header, so this is a hand-rolled fetch()-based SSE reader
// instead (per the approved plan). ~30 lines of frame parsing, no library.

import { API_BASE_URL, getRefreshedAccessToken } from "./client";
import { authStore } from "../store/authStore";
import type { ChatRequest, ChatStreamEvent } from "./types";

function parseFrame(raw: string): ChatStreamEvent | null {
  let eventName: string | null = null;
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (!eventName) return null;
  const data = dataLines.length > 0 ? JSON.parse(dataLines.join("")) : {};
  return { event: eventName, data } as ChatStreamEvent;
}

async function openStream(body: ChatRequest, accessToken: string | null): Promise<Response> {
  return fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(body),
  });
}

export async function* streamChat(body: ChatRequest): AsyncGenerator<ChatStreamEvent> {
  let response = await openStream(body, authStore.getState().accessToken);

  if (response.status === 401) {
    const newAccessToken = await getRefreshedAccessToken();
    response = await openStream(body, newAccessToken);
  }

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawFrame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseFrame(rawFrame);
      if (parsed) yield parsed;
      boundary = buffer.indexOf("\n\n");
    }
  }
}
