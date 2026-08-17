// src/apiService.ts
const API_URL = 'http://localhost:8000/chat';

interface ChatRequestBody {
  input: string;
  session_id: string;
}

/**
 * Stream chat messages from the backend (Server-Sent Events style)
 */
export async function streamChatMessage(
  input: string,
  sessionId: string,
  token: string,
  onMessage: (chunk: string) => void
): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(API_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify({ input, session_id: sessionId } as ChatRequestBody),
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  // Read stream
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      // Process any remaining buffered content
      if (buffer) {
        const lines = buffer.split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith('event:')) continue;
          if (trimmed.startsWith('data:')) {
            const data = trimmed.replace(/^data:\s*/, '');
            const normalized = data.toLowerCase().replace(/[\[\]]/g, '').trim();
            if (normalized === 'done') {
              return;
            }
            onMessage(data + '\n');
          } else {
            const normalized = trimmed.toLowerCase().replace(/[\[\]]/g, '').trim();
            if (normalized === 'done') {
              return;
            }
            const cleaned = trimmed.includes('data:')
              ? trimmed.substring(trimmed.indexOf('data:') + 5).trimStart()
              : trimmed;
            onMessage(cleaned + '\n');
          }
        }
      }
      break;
    }

    // Append chunk to buffer and process complete lines
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;

      if (line.startsWith('data:')) {
        const data = line.substring(5).trimStart();
        const normalized = data.toLowerCase().replace(/[\[\]]/g, '').trim();
        if (normalized === 'done') {
          return;
        }
        onMessage(data + '\n');
      } else if (line.trim().startsWith('event:')) {
        continue;
      } else {
        const content = line.trim();
        if (!content) continue;
        const normalized = content.toLowerCase().replace(/[\[\]]/g, '').trim();
        if (normalized === 'done') {
          return;
        }
        const cleaned = content.includes('data:')
          ? content.substring(content.indexOf('data:') + 5).trimStart()
          : content;
        onMessage(cleaned + '\n');
      }
    }
  }
}
