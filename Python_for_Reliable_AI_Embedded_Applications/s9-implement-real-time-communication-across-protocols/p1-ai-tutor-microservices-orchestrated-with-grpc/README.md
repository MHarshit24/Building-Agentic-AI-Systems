## Study Buddy: AI Tutor - Orchestrated Microservices with gRPC

This practice exercise demonstrates an orchestrated microservices architecture where an Orchestrator Agent coordinates multiple AI services (Gemini and Ollama) using gRPC protocol.

### Architecture

The system uses an Orchestrator Agent pattern that coordinates:
- Prompt Manager (gRPC service)
- Ollama Service (gRPC service)
- Gemini API (HTTP)

### Problem Statement

Build an AI Tutor Orchestrator that connects multiple microservices efficiently using the gRPC protocol. Define .proto contracts to establish a shared communication structure and generate Python code from them.​

​Implement a gRPC server (Prompt Manager) to serve prompt data and a client (Orchestrator) to request it. Simulate coordination between the Orchestrator, Prompt Manager, and local AI service to exchange data in real time.

### Context

Your AI Tutor system is evolving into a distributed architecture where multiple services must communicate seamlessly. The Orchestrator Agent now needs to fetch prompts, call LLMs, and combine responses efficiently without relying on slow, text-based REST calls.​

​To achieve this, you’ll implement gRPC-based communication between the Orchestrator and its internal microservices (like the Prompt Manager and local AI service). Define a shared .proto contract, generate Python code, and build both server and client components. This ensures fast, type-safe, and scalable interservice communication—ready for real-world, high-performance AI systems.

### Task Details
Following steps should be performed to build the solution for this practice. ​

**Step 1: Create `.proto` contracts​**

- Define `prompts.proto` (PromptManager) and `ollama_service.proto` (OllamaService) with request/response messages and RPCs.

**Step 2: Generate Python bindings​**

- Install `grpcio / grpcio-tools` and run protoc to produce `*_pb2.py` and `*_pb2_grpc.py` for both proto files.

**Step 3: Implement Ollama gRPC server​**

- Complete `OllamaServiceServicer.GenerateExplanation` to call the Ollama HTTP API, parse the response, and return the proto response.​
- Start a gRPC server (port 50052) and register the service.​

**Step 4: Implement Prompt Manager gRPC server​**

- Complete `PromptManagerServicer.GetPrompt` to look up prompts and return PromptResponse.​
- Start a gRPC server (port 50051) and register the service.

**Step 5: Implement the Orchestrator client​**

- Create gRPC channels/stubs to Prompt Manager and Ollama.​
- Implement `get_system_prompt`, `call_ollama`, and `orchestrate_dual_explanation` to fetch prompt, call Gemini (HTTP), call Ollama (gRPC), and combine results.​
- Add proper error handling and graceful degradation.

**Step 6: Wire up FastAPI main.py and test end-to-end**

- Initialize `OrchestratorAgent` in the FastAPI app, implement the `/explain/dual` endpoint to call the orchestrator, and convert results to response models.​
- Run servers and client, then validate using two terminals (server(s) + client/API).

**Expected Program Behavior:**

When the program runs:​
- The gRPC Prompt Manager and Orchestrator services start on separate ports.​
- The Orchestrator acts as a client, connecting to the Prompt Manager via gRPC.​
- Prompt requests are sent as binary messages defined in the .proto contract.​
- Responses are returned instantly with system prompts or model results.​
- The architecture showcases low-latency, structured interservice communication between AI components.

### Note:

**Complete the solution code as per the instructions given as comments in the respective files.**

## Project Structure
```
ai_tutor_orchestrated_microservices_with_gRPC/
├── app/
│   ├── proto/
│   │   ├── __init__.py
│   │   ├── prompts.proto
│   │   ├── prompts_pb2.py
│   │   ├── prompts_pb2_grpc.py
│   │   ├── ollama_service.proto
│   │   ├── ollama_service_pb2.py
│   │   └── ollama_service_pb2_grpc.py
│   ├── server/
│   │   ├── __init__.py
│   │   ├── prompt_manager_server.py
│   │   └── ollama_server.py
│   ├── __init__.py
│   ├── main.py
│   ├── orchestrator_agent.py
│   └── schemas.py
├── pyproject.toml
├── pytest.ini
└── README.md
```


### Setup

#### Prerequisites

1. Install Ollama from [ollama.com](https://ollama.com/download)

2. Download the model:
```bash
ollama pull gemma3:270m
```

3. Create `.env` file with your Gemini API key:
```
GEMINI_API_KEY=your-api-key-here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL=gemini-2.0-flash
```

Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

#### Install Dependencies

```bash
cd project_name
uv sync
```

### Running the Application

You need 3 terminals to run all services:

#### Terminal 1: Start Prompt Manager
```bash
uv run python -m app.server.prompt_manager_server
```

#### Terminal 2: Start Ollama Service
```bash
uv run python -m app.server.ollama_server
```

#### Terminal 3: Start FastAPI Server
```bash
uv run uvicorn app.main:app --reload --port 8000
```

### API Endpoints

#### POST /explain/dual
Get explanations from both Gemini and Ollama

Request:
```bash
curl -X POST "http://localhost:8000/explain/dual" \
  -H "Content-Type: application/json" \
  -d '{"concept": "RAG"}'
```

Response:
```json
{
  "concept": "RAG",
  "gemini_response": {
    "model": "gemini-2.0-flash",
    "explanation": "...",
    "success": true,
    "error_message": ""
  },
  "ollama_response": {
    "model": "gemma3:270m",
    "explanation": "...",
    "success": true,
    "error_message": ""
  }
}
```

### Interactive API Documentation

Open in browser:
```
http://localhost:8000/docs
```