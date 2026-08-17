# 📚 Study Buddy – AI Tutor REST API



A production-ready FastAPI application that transforms a console-based AI tutor into a scalable REST API with:



- 🌩 Cloud LLM integration (Gemini)

- 🖥 Local LLM integration (Ollama – `phi3:mini`)

- ⚡ Real-time streaming responses

- 🛡 Rate limiting (3 requests/minute per user)

- 📖 Auto-generated OpenAPI documentation



----



## 🎯 Homework Assignment



### Problem Statement



Transform your console-based AI Tutor into a FastAPI-powered REST API. ​



Implement endpoints for both cloud and local LLM queries, add streaming responses, apply rate limiting, and generate OpenAPI documentation. ​



---



#### Context



A learning platform needs to scale their AI Tutor beyond console access to serve multiple learners across web and mobile platforms simultaneously.  



They require an API that:

- Provides **real-time streaming responses**  

- Protects server resources with **rate limiting**  

- Maintains **auto-generated documentation**  

- Supports both **cloud (e.g., Gemini)** and **local (Ollama)** model integration  



---



#### Task Details



Following steps should be performed to build the solution for this practice. 



### Step 1: Prepare Your Project & Dependencies 



- Install the required libraries — `openai` for API interaction and `python-dotenv` for secure environment management.​

- Verify that your environment is properly initialized before proceeding.



### Step 2: Install and Configure Ollama for Local Model Execution



- Download and install `Ollama` from its official website.​

- Pull the required `Llama 3.1 (8B)` model using the terminal command `ollama pull llama3.1:8b`.​

- Ensure the Ollama service is running in the background to enable local model interaction.



### Step 3: Configure Cloud Model Access 



- Obtain a Gemini API key and store it securely in a `.env` file within your project folder.​

- Add the key and endpoint details.​

- Load these credentials securely into your application using the dotenv module.



### Step 4: Build and Execute the Tutor Agent 



- Develop a Python script that orchestrates both models — the cloud model (Gemini) for factual responses and the local model (Llama 3.1) for creative, private personalization.​

- Accept user queries, process them through both models, and display the results in a clear console format.​

- Run your program using `uv run main.py`.​

- Test the flow with example queries like “What is RAG?” or “Explain Agentic AI.”



**Hint:** 

- You'll need to implement the `get_cloud_explanation_streaming` and `get_local_personalization` functions, as well as the `main` function to handle the user interaction and model integration.

- **Prompt for local model:**

```

f"Rewrite this technical explanation in a highly engaging, fun, and personally relatable story or analogy for a beginner student exploring Agentic AI. Be creative and do not exceed 4 sentences. The explanation is:\n\n---\n{gemini_explanation}"



```



### Step 5: Set up the FastAPI project and dependencies​



- Initialize a FastAPI project and install all required libraries (`fastapi`, `uvicorn`, `slowapi`, `python-dotenv`, `openai`).​

- Create an `.env` file to store API keys and configuration variables for your cloud model (e.g., Gemini).



### Step 6: Define Pydantic models for request and response validation.



- Inside the `schemas.py` file add models to structure input (concept requests) and output (explanations with metadata) and error responses.​

- Use these schemas in your API endpoints for cleaner, consistent data handling.



### Step 7: Expose REST API endpoints​



- Define multiple endpoints in your FastAPI app:​

    - `/explain` → Uses a cloud model to provide structured explanations.​

    - `/personalize` → Uses a local model (via Ollama) for creative responses.​

    - `/explain/stream` → Implements Server-Sent Events (SSE) for real-time output streaming.



### Step 8: Implement rate limiting and error handling​



- Integrate `slowAPI` to set per-user rate limits (e.g., 3 requests/min).​

- Handle common API errors such as invalid keys, missing inputs, or timeouts with clear status codes and messages (400, 401, 429, etc.).



### Step 9: Document your API with OpenAPI​



- Leverage FastAPI's built-in **Swagger UI** and **ReDoc** for auto-generated documentation.​



|Tool| path |Purpose|

|---|---|---|

|Swagger UI|`/docs`|Interactive live testing|

|ReDoc|`/redoc`|Clean, read-only API reference|

|OpenAPI Schema|`/openapi.json`|Machine-readable contract​



- Include meaningful docstrings and response examples in your endpoint definitions.



----



#### Expected Program Behavior



When the program runs:​



- API server starts with Cloud (Gemini) and Local (Llama 3.1) models initialized.​

- Interactive Swagger UI available at /docs for testing endpoints.​

- `/explain` returns factual explanations from the cloud model in JSON.​

- `/explain/stream` streams explanations word-by-word in real-time.​

- `/personalize` returns creative, personalized explanations from the local model.​

- Rate limiting ensures excessive requests are blocked with 429 errors.



----



---



## 🚀 Overview



This project demonstrates how to build an AI-powered backend service using **FastAPI**, integrating both:



- **Cloud Model** → Gemini (structured, factual explanations)

- **Local Model** → Ollama (`phi3:mini`) for creative personalization



The API supports both standard JSON responses and real-time streaming responses.



---



## 🏗 Project Architecture



```

p1-ai-tutor-with-rest-api/

│

├── app/

│   ├── main.py

│   ├── schemas.py

│   └── __init__.py

│

├── requirements.txt

└── README.md

```



---



## ⚙️ Environment Configuration



Create a `.env` file in the root directory:



```env

GEMINI_API_KEY=your_gemini_api_key

GEMINI_ENDPOINT=https://generativelanguage.googleapis.com/

GEMINI_MODEL=gemini-1.5-flash

```



## 📦 Installation



### 1️⃣ Create virtual environment

```bash

python -m venv venv

```



Activate it:



**Windows**

```bash

venv\Scripts\activate

```



**Mac/Linux**

```bash

source venv/bin/activate

```



### 2️⃣ Install dependencies

```bash

pip install fastapi uvicorn slowapi python-dotenv requests google-generativeai

```



### 3️⃣ Install and Run Ollama (Local Model)



Make sure Ollama is installed and running:

```bash

ollama list

```



Pull the required model if not available:

```bash

ollama pull phi3:mini

```



## ▶️ Running the Application



From inside `p1-ai-tutor-with-rest-api`:

```bash

uvicorn app.main:app --reload

```



Server runs at:

```

http://127.0.0.1:8000

```



## 📖 API Documentation



FastAPI automatically generates documentation:



| Tool | URL | Purpose |

|------|-----|---------|

| Swagger UI | `/docs` | Interactive testing |

| ReDoc | `/redoc` | Clean API reference |

| OpenAPI Schema | `/openapi.json` | Machine-readable API contract |



## 🔌 API Endpoints



### 1️⃣ `/explain`



**Cloud Gemini Model**



Returns structured, factual explanation.



**Request**

```json

{

  "concept": "Recursion",

  "level": "beginner"

}

```



**Response**

```json

{

  "concept": "Recursion",

  "explanation": "...",

  "model_used": "Cloud Model: gemini-1.5-flash",

  "confidence": 0.95

}

```



### 2️⃣ `/personalize`



**Local Ollama Model (phi3:mini)**



Returns creative, analogy-based explanation.



**Response Example**

```json

{

  "concept": "Recursion",

  "explanation": "...",

  "model_used": "Local Model: phi3:mini",

  "confidence": 0.85

}

```



### 3️⃣ `/explain/stream`



Streams structured explanation from Gemini in real-time.



- Uses StreamingResponse

- Streams chunk-by-chunk

- Media type: text/plain



⚠️ **Note**: Swagger UI buffers streaming. Use curl to see live streaming:



```bash

curl -N -X POST http://127.0.0.1:8000/explain/stream \

-H "Content-Type: application/json" \

-d "{\"concept\":\"recursion\",\"level\":\"beginner\"}"

```



### 4️⃣ `/personalize/stream`



Streams creative explanation from local Ollama model.



- Parses streaming JSON chunks

- Extracts "response" field

- Yields text token-by-token



## 🛡 Rate Limiting



Integrated using slowapi.



- Limit: 3 requests per minute per user

- Returns HTTP 429 if exceeded



Example error:

```json

{

  "error": "Rate limit exceeded",

  "detail": "Maximum 3 requests per minute allowed."

}

```



## 🧠 Key Concepts Implemented



- FastAPI routing & dependency injection

- Pydantic request/response models

- Environment variable management

- Cloud + Local LLM integration

- Streaming responses with async generators

- Parsing streamed JSON from Ollama

- Rate limiting middleware

- Exception handling with HTTP status codes

- OpenAPI auto-documentation



## 🎯 Expected Behavior



When running:



- API initializes Gemini client

- Connects to local Ollama model

- Swagger UI available at /docs

- Structured cloud explanations available

- Creative local explanations available

- Streaming works via terminal (curl)

- Rate limiting protects API from abuse