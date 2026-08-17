## Project Context

In earlier practice, your **Travel & Trip Planner Agent** became stateful — it could remember destinations, activities, and preferences across sessions using `RunnableWithMessageHistory`.  
Now, it’s time to give that intelligent backend a **face**. In this sprint, you’ll learn to build user-friendly **frontends** so travelers can actually chat with your agent instead of using terminal commands.  

---

## Problem Statement

Design and implement interactive frontends that connect to your existing **stateful travel agent backend** built in earlier practice.  
You will complete **one major tasks**:  

### **Task 1 — Connect a React Frontend to the FastAPI Agent**

#### Goal  
Build a React chat UI that communicates with your FastAPI `/chat` endpoint, sending both the user’s message and the `session_id` to maintain conversation memory.

#### Requirements  
1. **Backend**  : Use the provided boilerplate.
   - Add CORS middleware to allow requests from `http://localhost:5173` (Vite default port) and `http://localhost:3000`.  
2. **Frontend** : Use the provided React boilerplate.  
   - In `apiService.ts`: define `streamChatMessage(input, sessionId, onMessage)` using `fetch()` with ReadableStream to handle streaming responses from your FastAPI endpoint.  
   - In `ChatComponent.tsx`:  
     - Use `useState()` for `messages`, `input`, `sessionId`, and `isLoading`.  
     - Generate `sessionId` once via `uuidv4()` in `useEffect()`.  
     
3. Start both servers:  
   ```bash
   # Backend
   cd backend
   uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   
   # Frontend (in a separate terminal)
   cd frontend
   npm run dev
   ```  
4. Test a full conversation in your browser at `http://localhost:5173` (Vite default port).


> Implementation note: The backend is implemented in `main.py` with CORS middleware configured for localhost:5173 and 3000, enabling secure cross-origin requests. The `/chat` endpoint uses Server-Sent Events to stream AI responses token-by-token, maintaining session state via `RunnableWithMessageHistory`. The frontend's `apiService.ts` handles streaming with `fetch()` and `ReadableStream`, parsing event data to update the UI in real-time. `ChatComponent.tsx` manages chat state, generates unique session IDs, and displays streaming messages with error handling for a smooth user experience.


---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **CORS Setup**: Make sure backend CORS middleware is correctly configured so the frontend at localhost:5173 or localhost:3000 can send requests without being blocked.
2. **Streaming Read in Frontend**: Make sure the frontend correctly reads streamed chunks using ReadableStream, decodes them, and forwards meaningful data: lines to the message handler.
3. **Streaming Display**: Ensure the frontend smoothly displays streaming AI responses from the backend and handles any errors gracefully.
  
