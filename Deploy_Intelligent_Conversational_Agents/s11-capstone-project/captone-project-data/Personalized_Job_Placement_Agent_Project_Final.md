# Personalized Job Placement Agent - Your AI-Powered Career Assistant

An intelligent conversational agent that helps users discover relevant job opportunities, analyze their resumes, identify skill gaps, and generate personalized cover letters tailored to specific job descriptions.

---

## Problem Statement: Personalized Job Placement Agent

### Context

In today's competitive job market, job seekers face numerous challenges when searching for opportunities and crafting application materials. Traditional job search platforms require users to manually browse through hundreds of listings, match their skills to job requirements, and create customized application materials for each position—a time-consuming and often overwhelming process.

**Common Challenges:**

- **Information Overload:** Job seekers are overwhelmed by the sheer volume of job postings across multiple platforms, making it difficult to identify relevant opportunities.
- **Lack of Personalization:** Generic job recommendations fail to consider individual skills, experience levels, and career goals.
- **Manual Resume Analysis:** Users struggle to identify skill gaps and understand how their resume compares to job requirements.
- **Time-Intensive Application Process:** Creating personalized cover letters for each job application is time-consuming and repetitive.
- **Fragmented Tools:** Job search, resume analysis, and cover letter generation are typically handled by separate tools, requiring users to switch between multiple platforms.
- **Limited Context Awareness:** Most job search tools don't maintain conversation context or remember user preferences across sessions.

### Project Goal

Develop an **AI-powered Job Placement Agent** that provides a conversational interface to help users discover relevant job opportunities, analyze their resumes against job requirements, identify skill gaps, and automatically generate personalized cover letters—all through an intelligent, context-aware conversation.

---

## Problem Description

This project focuses on building a **full-stack Job Placement Agent Application** that:

- Interacts conversationally with users to understand their job preferences, experience level, location, and career goals.
- Fetches real-time job listings from external APIs **(Note: The APIs mentioned below are suggestions. You are free to use other job search/career APIs that suit your needs - SerpAPI for Google Jobs and Rise API for career insights).**
- Analyzes user resumes to extract skills and compare them against job requirements.
- Identifies skill gaps and provides actionable improvement suggestions.
- Generates personalized, professional cover letters tailored to specific job descriptions and user backgrounds.
- Maintains conversation context and user preferences throughout the session.
- Provides observability and monitoring through Langfuse integration.

---

## Functional Requirements

### 1. Conversational Job Placement Assistant

A chat-based AI agent that can:
- Collect user details such as:
  - Preferred job role
  - Years of experience
  - City or preferred location
  - Uploaded/pasted resume text
- Maintain conversation context across multiple messages.
- Understand when to search for jobs vs. when to analyze a resume vs. when to generate a cover letter.
- Dynamically route conversations based on user intent.

### 2. External Job Search Integration

 You can use the suggested APIs below or choose alternative job search/career APIs that better fit your project needs.

The agent must be capable of calling external APIs to fetch live job openings:
- **Google Jobs API via SerpAPI**: https://serpapi.com/google-jobs-api?utm_source=chatgpt.com
- **Rise API** (career roles, skills, job insights): https://docs.joinrise.co/

**Disclaimer: The API key generation link provided may be subject to a paid version. You have full discretion to switch to an alternative API key or plan based on your project requirements.**

The agent should automatically select which API/tool to call based on the user request.

### 3. Real-Time Job Discovery

When the user provides a job role + city, or after analyzing a resume:
- Fetch at least 5–10 live job listings.
- Display job title, company, location, summary, and link.
- Present results in a user-friendly format.

### 4. Resume & Skill Gap Analysis

After the user shares a resume:
- Extract key skills from the resume.
- Compare against skills found in fetched job descriptions.
- Identify missing or weak areas.
- Provide a clear, actionable list of resume improvement suggestions.

### 5. Personalized Cover Letter Generator

For any selected job posting, the agent must generate a personalized, professional cover letter that:
- Uses details from the job description.
- Uses details from the user's resume and experience.
- Reflects appropriate tone and structure.
- Is tailored to the specific role and company.

### 6. Multi-Step Workflow Implementation

The job placement agent must operate through a structured, multi-step workflow. Examples include:
- Route 1: User asks for job recommendations → Fetch jobs → Summarize requirements → Present list
- Route 2: User uploads resume → Extract skills → Identify gaps → Suggest improvements
- Route 3: User selects a job → Generate cover letter

The system should dynamically choose the correct flow based on user input.

### 7. Short-Term Conversation Memory

The agent must remember important details during the session, such as:
- User's city
- Target role
- Experience level
- Resume content
- Previously viewed job postings

Memory should reset when the session ends.

### 8. FastAPI Backend

Your backend will:
- Expose protected endpoints for chat interactions (if authentication is implemented).
- Host the agent pipeline built with LangChain.
- Implement model calls, prompts, memory, and tool integrations.
- Log traces to Langfuse for observability.

### 9. Observability with Langfuse

Instrument the agent so that:
- Every agent run produces a trace in Langfuse.
- You can view:
  - LLM responses
  - Tool calls
  - Latency
  - Errors or retries
  - Multi-step workflows

You must include screenshots of Langfuse traces in your final submission.

### 10. Secure Authentication with Auth0 

**Note:** Authentication is optional. If implemented:
- Users must log in before accessing the chat or job search features.
- The frontend must obtain a JWT and pass it to the FastAPI backend.(Optional)
- The FastAPI backend must validate the JWT before processing agent requests.(Mandatory)

### 11. Frontend (Streamlit/React/HTML,CSS,JavaScript)(Optional)

**Note:** Frontend design is optional. If implemented, consider including:
- Login/logout via Auth0 (if authentication is implemented)
- Chat interface for interacting with the agent
- Resume upload or paste area
- Display panel for job listings
- Button to "Generate Cover Letter" for a selected job
- Sections for showing analysis results



---

## Technical Details

**Programming Languages:** Python (Backend), TypeScript/JavaScript (Frontend)

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
Add all the necessary environment variables. In the project, you can use either the Gemini model or the Azure OpenAI model for LLM calls.

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
2. External API Integration (Required - can use SerpAPI/Rise API or alternative job search APIs)
3. Langfuse Observability Dashboard (Required)
4. Frontend Application (React/Streamlit/HTML,CSS,JavaScript or any UI implementation in the project)
5. Authentication with Auth0 (Backend required)
6. README.md including:
   - Setup instructions
   - Architecture diagram
   - Sample workflows
   - Langfuse screenshot
   - API endpoints documentation

---

## Goal

Build a production-grade intelligent agent that combines LLM reasoning, tool calling, workflow orchestration, observability, authentication, and full-stack UI/UX—similar to modern AI-driven applications.

