## Project Context

You are continuing as the lead developer of the **Travel & Trip Planner Agent**, an AI-powered system that helps users plan trips based on their preferences, budget, and destination.  

In earlier practice, you built the core suggestion engine and learned how to make synchronous and asynchronous LLM calls using **LangChain**, **Gemini**, and **FastAPI**.  

In this practice, you will **enhance this engine** by integrating advanced LangChain capabilities such as **prompt templates**, **few-shot prompting**, and **structured output parsing**. By the end, you will have a robust and intelligent trip planner that can produce structured, contextual, and reliable travel recommendations.

---

## Problem Statement

Enhance your **Travel & Trip Planner Agent** by integrating advanced LangChain features for dynamic prompt management, personalized recommendations, and structured output generation.  
You will complete **three main tasks**:

---

### **Task 1 — Fetch Dynamic Prompt from Langfuse**

#### Goal  
Demonstrate dynamic prompt generation from an external source (Langfuse) instead of local templates, creating prompts that adapt to user inputs such as destination, duration, and budget.

#### Requirements  
1. **Langfuse Connection**
   - Connect to Langfuse using your API credentials.

2. **Prompt Template Setup**
   - Fetch a pre-defined prompt template from Langfuse (e.g., `travel_itinerary`).
   - Configure the prompt with appropriate settings (e.g., label: `production`, temperature: `0.7`).
   - Define a prompt template in Langfuse with placeholders such as `{destination}`, `{days}`, and `{budget}`.

3. **API Endpoint**
   - Create a FastAPI endpoint `/task1` that accepts query parameters: `destination`, `days`, and `budget`.
   - Fetch the template from Langfuse and fill the placeholders with user inputs.
   - Use the fetched template to generate the LLM prompt.

4. **LLM Invocation**
   - Invoke the LLM (Gemini) with the generated prompt and return the itinerary response.

### Implementation details in main.py:
   - `Langfuse` client created from env vars: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
   - `/task1` is a POST endpoint accepting JSON body `ItineraryRequest` with `destination`, `days`, `budget`.
   - Uses `langfuse.get_prompt("niit_agentic_ai_travel_itinerary_generator_v1", label="production")`.
   - Compiles prompt with values then `llm.invoke(compiled_prompt)`.
   - Returns `{"itinerary": response.content}`.
   - Raises 404 if prompt missing and 500 on any other exception.

---

### **Task 2 — Few-Shot Prompting for Personalized Recommendations**

#### Goal  
Teach the model to produce better recommendations by using few-shot examples to guide the model's output style and context.

#### Requirements  
1. **Prompt Template Setup**
   - Use `ChatPromptTemplate` to define a system message and example interactions.
   - Include examples that demonstrate different travel scenarios (e.g., solo traveler, couple, family).
   - Show how each example should be formatted in the response.

2. **API Endpoint**
   - Create a POST endpoint `/task2` that accepts a user query.

3. **Few-Shot Prompt Construction**
   - Combine the examples and user input into a single few-shot prompt.

4. **LLM Invocation**
   - Invoke the LLM (Gemini) with the few-shot prompt and return the personalized itinerary.

### Implementation details in main.py:
   - `/task2` is a POST endpoint with JSON body `UserQuery` containing `query`.
   - Builds few-shot context using `ChatPromptTemplate.from_messages([("system", ...), ("human", ...), ("ai", ...), ...])`.
   - Uses chain operator `prompt | llm` and `chain.invoke({"query": user.query})`.
   - Returns `{"result": response.content}`.
   - Catches exceptions and maps to HTTP 500.

---

### **Task 3 — Structured Output Parsing for Trip Data**

#### Goal  
Ensure the model outputs structured JSON that can be easily stored or visualized on the frontend by using Pydantic models and LangChain's output parsers.

#### Requirements  
1. **Pydantic Schema Definition**
   - Define a Pydantic model (e.g., `TripPlan`) with fields such as:
     - `destination` (str)
     - `days` (int)
     - `estimated_cost` (str)
     - `highlights` (list of strings)

2. **Output Parser Setup**
   - Use LangChain's `PydanticOutputParser` to enforce structured output from the LLM.

3. **API Endpoint**
   - Create an endpoint `/task3` that accepts user input (`destination`, `days`, `budget`).

4. **LLM Invocation and Parsing**
   - Format the prompt with the output parser instructions.
   - Invoke the LLM and parse the response using the PydanticOutputParser.

5. **Response**
   - Return a JSON response following your `TripPlan` schema.

### Implementation details in main.py:
   - `TripPlan` model includes `destination`, `days`, `estimated_cost`, `highlights` (List[str]).
   - `TripPlanRequest` input model includes `destination`, `days`, `budget`.
   - `/task3` is a POST endpoint that builds `ChatPromptTemplate.from_messages` with system + human instruction, including `format_instructions` from `PydanticOutputParser`.
   - The prompt is rendered via `prompt.format_messages(...)` and then `llm.invoke(formatted_prompt)`.
   - Output is parsed via `parsed = parser.parse(response.content)` and returns `parsed.dict()`.
   - Catches `ValidationError` (400) and general exceptions (500).

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **LLM Setup**: Make sure your LLM models are initialized correctly using environment variables and the specified temperature and retry settings.
2. **Environment Loading**: Ensure your .env file is loaded properly and required keys like GEMINI_API_KEY are validated before starting the app.
3. **FastAPI Setup**: Make sure the FastAPI app is initialized correctly with appropriate routes and descriptive titles
4. **Langfuse Integration**: Ensure the Langfuse client is configured with the right keys and used to fetch prompts dynamically.
5. **Task 1 Implementation**: Make sure the travel itinerary prompt is fetched from Langfuse, formatted with user inputs, and sent to the LLM for a response.
6. **Task 2 Few-Shot Prompting**: Ensure ChatPromptTemplate.from_messages() is used correctly with few-shot examples and dynamic user queries.
7. **Task 3 Structured Output**: Make sure Pydantic models and PydanticOutputParser are used to validate and return structured trip plan data.
8. **Error Handling**: Ensure appropriate HTTP exceptions are raised for missing prompts, validation errors, and general failures.
9. **Response Formatting**: Make sure all task endpoints return clean JSON responses with clear field names for easy consumption.
10. **App Execution**: Ensure the app runs correctly with uvicorn as the entry point and reload is enabled for development

