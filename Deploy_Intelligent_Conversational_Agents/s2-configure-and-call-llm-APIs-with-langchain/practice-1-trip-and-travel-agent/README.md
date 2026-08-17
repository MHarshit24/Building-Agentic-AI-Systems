## Project Context

You are the lead developer for the new **Travel & Trip Planner Agent**. Your first major goal is to build the core "suggestion engine" — the component responsible for all interactions with the Large Language Model (LLM).  

In this practice, you will build this engine using **LangChain** and **FastAPI**. You'll start with a baseline synchronous version, then add versatility with different output modes, and finally implement asynchronous patterns for modern, responsive APIs.

---

## Problem Statement

Design and implement the core suggestion engine for your **Travel & Trip Planner Agent** using **LangChain** and **FastAPI**.  
You will complete **three main tasks**:

---

## Implementation Overview

Your implementation in `main.py` includes:

- Environment handling via `.env` (loads `GEMINI_API_KEY`, `GEMINI_OPENAI_ENDPOINT`, `GEMINI_MODEL`).
- `ChatOpenAI` base instance with `temperature=0.3`, `max_retries=2` for general use.
- `POST /task1` using `TripRequest` (`destination`, `theme`, `days`) and returning generated itinerary JSON with HTTPException error handling.
- `POST /task2` using `PromptRequest` (single `prompt`) with:
  - `factual_llm` (`temperature=0.2`, `max_tokens=150`)
  - `creative_llm` (`temperature=0.9`, `max_tokens=300`)
  - returns both `factual` and `creative` outputs with HTTPException error handling.
- `POST /task3` using `AsyncSuggestionRequest` (`question`) with async endpoint calling `await generate_async_suggestion()` directly, returning `AsyncSuggestionResponse` with HTTPException error handling.

### Quick confirm by running

```
uvicorn main:app --reload --port 8000
```

and test endpoints for JSON outputs as described below.

---

### **Task 1 — Baseline Itinerary Generator (Synchronous)**

#### Goal  
Build the foundational version of the travel suggestion engine that synchronously invokes the LLM to generate travel itineraries.

#### Requirements  
1. Set up your environment file with gemini key.

2. **LLM Instantiation** — Import your LLM class (e.g., `ChatOpenAI`) and instantiate it with your chosen model name and reliability parameters (e.g., `max_retries=2`).

3. **API Endpoint**
   - Create a FastAPI POST endpoint `/task1` that accepts user inputs:
     - `destination` (e.g., "Paris")
     - `theme` (e.g., "museums and parks")
     - `days` (e.g., `4`)
   - Construct a prompt from these inputs (e.g., "Suggest a 4-day itinerary for a family trip to Paris, focusing on museums and parks.").

4. **Invocation**
   - Use the appropriate method to call the LLM with the constructed prompt.

5. **Output**
   - Return a JSON response containing the generated itinerary.

---

### **Task 2 — Adding Versatility with Factual & Creative Modes**

#### Goal  
Enhance the travel agent to adapt to different user preferences by providing both factual and creative response styles controlled by LLM hyperparameters.

#### Requirements  
1. **Factual Mode**
   - In the FastAPI POST endpoint `/task2`, accept a JSON body with a key (such as `factual_prompt`).
   - Instantiate a language model with low temperature (for more deterministic responses) and a limit on maximum output tokens (for concise output).
   - Use the model's method to generate the response.
   - Return the output in JSON format.

2. **Creative Mode**
   - In the same endpoint, accept another key for the creative input (e.g., `creative_prompt`).
   - Instantiate a separate language model with a higher temperature value (e.g., `temperature=0.9` for more creative outputs).
   - Use the model's appropriate method to generate the creative response.
   - Return the creative response in the output with a clear heading.

3. **Output**
   - The endpoint should return a combined JSON response showing both factual and creative outputs.

---

### **Task 3 — Learning the Asynchronous API**

#### Goal  
Implement asynchronous LLM invocation to enable non-blocking, concurrent operations for responsive APIs.

#### Requirements  
1. **Setup**
   - Import an asynchronous framework (e.g., `asyncio`).
   - Instantiate a single reusable language model instance with a moderate temperature value.

2. **FastAPI Endpoint**
   - Create a POST endpoint `/task3` that accepts a JSON body with a key: `question` (e.g., "Ask any question relevant to your use case.")

3. **Async Function**
   - Define an asynchronous function that performs an async operation and returns the result.

4. **Execution**
   - Ensure the async function is properly called within the FastAPI endpoint using an appropriate method for asynchronous execution.

5. **Output**
   - Return a JSON response.
---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **LLM Setup**: Make sure your LLM models are initialized correctly using environment variables (GEMINI_API_KEY, GEMINI_MODEL_NAME, GEMINI_BASE_URL) and the main model includes settings like temperature=0.3 and max_retries=2.
2. **Input Handling**: Make sure your FastAPI endpoints use Pydantic models to accept structured inputs and return clean JSON responses for all three tasks.
3. **Task1 Prompting**: Make sure `/task1` builds the full itinerary prompt properly using destination, theme, and days, and generates the response synchronously using llm.invoke().
4. **Task1 Output**: Make sure `/task1` extracts the LLM output correctly using result.content and handles errors with a clear HTTPException message.
5. **Task2 Models**: Make sure `/task2` uses two different LLM configurations where the factual model has low temperature and the creative model has high temperature.
6. **Task2 Responses**: Make sure `/task2` returns two separate responses (factual and creative) and both are generated using `.invoke()` with the same base prompt.
7. **Async Logic**: Make sure `/task3` uses the asynchronous function correctly by calling await `llm.ainvoke()` inside generate_async_suggestion.
8. **Async Execution**: Make sure `/task3` triggers the async call properly using `await` in the async endpoint and returns the output in the AsyncSuggestionResponse format.
9. **API Stability**: Make sure all three endpoints run without errors when starting the FastAPI application with uvicorn.

