// src/apiService.ts

// Task 1: Define the API base URL and request body structure (input, session_id) 
// in your React app to connect with the FastAPI /chat endpoint

const API_URL = "http://localhost:8000/chat";

//Task 2: Implement streamChatMessage() to send input and sessionId to /chat via fetch() and 
// validate the response before streaming.

export async function streamChatMessage(
  input: string,
  sessionId: string,
  onMessage: (chunk: string ) => void
) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      input: input,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to connect to server");
  }

  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let done = false;

  //Tas 3: Read and decode streamed chunks from the response, parse lines for data: events, and update messages 
  //in real time until [DONE] is received.

  while (!done) {
    const { value, done: doneReading } = await reader.read();
    done = doneReading;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split("\n");

    for (let line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.replace("data: ", "").trim();

        if (data === "[DONE]") return;

        onMessage(data);
      }
    }
  }
}
