# World News & Topic Summary Agent – Your AI-Powered News Companion

An intelligent conversational agent that fetches global news, summarizes long or complex articles, explains difficult topics in simple terms, and delivers personalized news digests based on user interests.

---

## Problem Statement: World News & Topic Summary Agent

### Context

In today’s digital world, people face significant challenges when trying to stay informed. News is scattered across thousands of sources, articles are often long or filled with jargon, and users struggle to track only the topics they care about. As a result, staying updated becomes overwhelming and time-consuming.

**Common Challenges:**

- **Information Overload:** Users are bombarded with countless news articles, making it difficult to identify what truly matters.
- **Complex & Lengthy Articles:** Many news pieces are technical, politically dense, or too long for quick consumption.
- **Lack of Personalization:** News platforms rarely tailor content to specific user interests or preferred reading styles.
- **Fragmented Sources:** Users switch across multiple apps or websites to gather updates.
- **Time Constraints:** Busy individuals want clear, concise summaries instead of reading full articles.
- **No Session Awareness:** Traditional news apps do not remember preferred topics or previously explored categories.

### Project Goal

Build an **AI-powered World News & Topic Summary Agent** that provides a conversational interface to deliver real-time news, simplify complex topics, and generate personalized, easy-to-read summaries—while remembering user preferences within a session.

---

## Problem Description

This project focuses on building a **full-stack News Assistant Application** that:

- Interacts conversationally with users to understand their news interests, preferred topics, and reading preferences.
- Fetches the latest headlines from **external news APIs (Note: The APIs mentioned below are suggestions. You are free to use other news APIs that suit your needs - NewsData.io, CurrentsAPI).**
- Summarizes long articles into short, simple, and detailed summaries.
- Simplifies complex geopolitical, economic, or scientific topics into beginner-friendly explanations.
- Delivers personalized daily digests based on user-selected topics.
- Maintains conversation context and short-term memory (favorite topics, last viewed categories).
- Provides complete observability using Langfuse to track agent reasoning, tool calls, and multi-step workflows.

---

## Functional Requirements

### 1. Conversational News Assistant

A chat-based AI agent that can:
- Understand user interests (e.g., politics, sports, technology, finance, climate).
- Maintain context across messages.
- Ask follow-up questions (e.g., preferred region, depth of summary).
- Decide when to:
  - Fetch news
  - Summarize articles
  - Simplify topics
  - Generate digests

### 2. External News Retrieval Integration

You can use the suggested APIs below or choose alternative news APIs that better fit your project needs.

Suggested external APIs:
- NewsData.io- https://newsdata.io/
- CurrentsAPI- https://currentsapi.services/en

**Disclaimer: The API key generation link provided may be subject to a paid version. You have full discretion to switch to an alternative API key or plan based on your project requirements.**

The agent must:
- Fetch latest news headlines on demand.
- Retrieve source details, URLs, and categories.
- Dynamically choose the correct API/tool based on intent.

### 3. Real-Time News Discovery

When the user asks for a topic:
- Fetch 5–10 recent headlines.
- Display:
  - Title
  - Description
  - Source
  - URL
  - Published date
- Present results in a clean, structured format.

### 4. Multi-Level Summaries & Topic Simplification

The agent must be able to:
- Generate 3 levels of summaries:
  1. **Simple summary** (beginner-friendly)
  2. **Detailed summary**
  3. **Bullet-point highlights**
- Simplify complex topics like:
  - Geopolitical conflicts
  - Economic policies
  - Scientific research
  - Global crises

### 5. Personalized Daily Digest

Users can request:
- A **daily personalized news digest** based on:
  - Favorite topics
  - Reading frequency
  - Preferred summary style  
- The system compiles a human-friendly summary of important updates.

### 6. Multi-Step Workflow Implementation

Example flows:
- Route 1: User asks for topic news → Fetch headlines → Summarize → Present results  
- Route 2: User shares a news link → Extract content → Summarize → Simplify  
- Route 3: User wants a daily digest → Fetch multi-topic news → Summarize → Compile digest  

The agent must automatically select the correct flow.

### 7. Short-Term Session Memory

The agent should remember during the session:
- User's favorite categories  
- Preferred complexity level  
- Previously viewed news topics  
- Preferred summary length  

Memory resets after session ends.

### 8. FastAPI Backend

Your backend will:
- Expose secure endpoints for chat interactions (if authentication is implemented)
- Host the agent pipeline using LangChain
- Implement memory, model calls, and all tool integrations
- Log traces to Langfuse

### 9. Observability with Langfuse

Track:
- LLM outputs
- Summaries generated
- API calls to news providers
- Workflow paths
- Latency
- Errors & retries

Include Langfuse traces in project submission.

### 10. Secure Authentication with Auth0

**Note:** Authentication is optional. If implemented:
- Users must log in to use the news assistant.
- The frontend must obtain a JWT and pass it to the FastAPI backend.(Optional)
- The FastAPI backend must validate the JWT before processing agent requests.(Mandatory)

### 11. Frontend (Streamlit/React/HTML,CSS,JavaScript)(Optional)

**Note:** Frontend design is optional. If implemented, consider including:
- Login/logout via Auth0 (if authentication is implemented)
- Chat interface with the agent
- Topic selection panel
- News summary display cards
- "Simplify this topic" and "Generate digest" buttons
- User preference settings

---

## Technical Details

**Languages:** Python (Backend), TypeScript/JavaScript (Frontend)

### Libraries & Tools

| Library/Tool | Purpose |
|-------------|---------|
| `fastapi` | Build backend API |
| `uvicorn` | Run FastAPI server |
| `langchain` | Build LLM workflows and agent pipelines |
| `langfuse` | Observability and tracing for LLM applications |
| `requests` | Communicate with external APIs (SerpAPI, Rise API) |
| `python-jose` | JWT token validation |
| `python-dotenv` | Manage environment variables securely |
| `react` | Build frontend user interface |
| `vite` | The Build Tool for the Web |
| `Streamlit` | Faster way to build and share Data Apps |
| `auth0-react` | Auth0 authentication integration for React |

### Environment Variables

| Variable | Purpose |
|---------|---------|
| `GEMINI_API_KEY` | Gemini API key for LLM integrations |
| `GEMINI_MODEL_NAME` | Gemini Model name for LLM integrations |
| `GEMINI_BASE_URL` | Gemini Base url for LLM integrations |
| `AUTH0_DOMAIN` | Auth0 domain for authentication |
| `AUTH0_CLIENT_ID` | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | Auth0 client secret |
| `AUTH0_AUDIENCE` | Auth0 API audience identifier |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key for authentication |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for authentication |
| `LANGFUSE_HOST` | Langfuse base url for authentication |
---

## Final Deliverables

1. FastAPI Backend with LangChain Agent (Required)
2. External API Integration (Required - can use NewsData.io / CurrentsAPI or alternative news APIs)
3. Langfuse Observability (Required)
4. Frontend Application (React/Streamlit/HTML,CSS,JavaScript or any UI implementation in the project)
5. Auth0 Authentication (Backend required)
6. README.md with:  
   - Setup instructions  
   - Architecture diagram  
   - Sample workflows  
   - Langfuse trace screenshots  
   - API documentation  

---

## Goal

Build a production-grade intelligent news agent that leverages LLM reasoning, tool calling, workflow orchestration, observability, authentication, and a full-stack UI—similar to modern AI-powered products.
