## Project Context

In earlier practice, your **Travel & Trip Planner Agent** became intelligent — it could classify and route queries such as **booking**, **cancellation**, or **general inquiries** using LCEL pipelines.  
However, the agent still suffered from amnesia — it forgot everything after each response.

In this practice, you will enable **short-term memory** for your agent so it can hold meaningful **multi-turn conversations**. Your upgraded agent will now **remember user details** like destination, duration, and preferences across messages in the same session.

---

## Problem Statement

Extend your **Travel & Trip Planner Agent** into a **stateful conversational agent** that remembers trip details across multiple turns using **LangChain Expression Language (LCEL)** components.  
Your agent should maintain context within the same session but start fresh for new sessions.  
You will complete **two main tasks**:

---

### **Task 1 — Create a Memory-Aware Prompt**

#### Goal  
Build a prompt that can accept and display conversation history using `MessagesPlaceholder` to make the agent memory-aware.

#### Requirements  
1. Create a `ChatPromptTemplate` that includes a system message, a `MessagesPlaceholder` for chat history, and a user input placeholder.

2. Test the prompt with manually created chat history to verify that conversation history is correctly inserted into the prompt.

3. Ensure the prompt structure allows the LLM to access and reference previous conversation turns when generating responses.


> Implementation note: The memory-aware prompt is implemented in `trip_memory_prompt.py`. It builds a `ChatPromptTemplate` with a system message, a `MessagesPlaceholder` for chat history, and a dynamic user message placeholder. The file also simulates persistent context with a manual history of alternating `HumanMessage` and `AIMessage` turns to verify the prompt behavior.

---

### **Task 2 — Build a Stateful Trip Planner API**

#### Goal  
Create a FastAPI-based AI agent that remembers trip details across turns within the same session using `RunnableWithMessageHistory`.

#### Requirements  
1. Implement a session management function that returns a unique chat message history for each session ID, initializing it if it doesn't already exist.

2. Create a `ChatPromptTemplate` that includes a `MessagesPlaceholder` for chat history to enable memory-aware conversations.

3. Build a core LCEL chain that combines the prompt with the LLM.

4. Wrap the core chain using `RunnableWithMessageHistory` to enable automatic memory management per session, configuring the input and history message keys appropriately.

5. Create a FastAPI endpoint `/new-session` that generates and returns a unique session ID for each new chat.

6. Create a FastAPI endpoint `/chat` that accepts user input and session ID, invokes the stateful chain with the appropriate configuration, and returns the session ID, user input, and agent's response.


> Implementation note: The API is implemented in `stateful_trip_agent.py`. It loads model configuration from `.env`, initializes `ChatOpenAI`, manages per-session history with `ChatMessageHistory`, wraps the prompt+LLM chain using `RunnableWithMessageHistory`, and exposes `/new-session` and `/chat` for session-aware conversations.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **LLM Initialization**: Make sure the ChatOpenAI model is initialized with the correct model name, API key, and base URL for consistent behavior across sessions.
2. **Memory Prompting**: Ensure the prompt correctly uses MessagesPlaceholder to include chat history and maintain continuity in travel-related conversations.
3. **Session Handling**: Make sure get_session_history correctly creates and retrieves ChatMessageHistory objects for unique session IDs.
4. **Stateful Chain**: Ensure RunnableWithMessageHistory is properly configured to pass session-specific memory and preserve conversation state.
5. **FastAPI Endpoints**: Make sure /new-session generates valid UUIDs and /chat correctly accepts input, session_id, and returns model responses tied to the correct session.
6. **Manual Memory Demo**: Ensure the memory-aware prompt in trip_memory_prompt.py correctly appends HumanMessage and AIMessage entries to simulate persistent conversation context


