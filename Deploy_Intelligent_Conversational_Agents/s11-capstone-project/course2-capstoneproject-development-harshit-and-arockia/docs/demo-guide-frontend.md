# Job Placement Agent — Frontend Demo Guide

**Project:** Course 2 Capstone — Intelligent Conversational Agent  
**Frontends:** HTML SPA (`index.html`) · Streamlit App (`app.py`)  
**Deployed URL:** See `.env` / Vercel dashboard for live URL  
**Local URLs:** HTML SPA → `http://localhost:5173` · Streamlit → `http://localhost:8501`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Frontend Comparison](#frontend-comparison)
3. [HTML SPA Demo (`index.html`)](#html-spa-demo-indexhtml)
   - [1. Loading Screen](#1-loading-screen)
   - [2. Login Screen](#2-login-screen)
   - [3. Guest Mode](#3-guest-mode)
   - [4. Main App Layout](#4-main-app-layout)
   - [5. Career Profile & Resume Sidebar](#5-career-profile--resume-sidebar)
   - [6. Quick Actions](#6-quick-actions)
   - [7. Job Search via Chat](#7-job-search-via-chat)
   - [8. Resume Analysis & Skill Gap](#8-resume-analysis--skill-gap)
   - [9. Cover Letter Generation](#9-cover-letter-generation)
   - [10. Multi-turn Conversation Memory](#10-multi-turn-conversation-memory)
   - [11. New Conversation & Session Reset](#11-new-conversation--session-reset)
   - [12. Connection Status Indicator](#12-connection-status-indicator)
   - [13. Logout](#13-logout)
4. [Streamlit App Demo (`app.py`)](#streamlit-app-demo-apppy)
   - [1. Starting the App](#1-starting-the-app)
   - [2. Sidebar — Status & User Info](#2-sidebar--status--user-info)
   - [3. Quick Action Buttons](#3-quick-action-buttons)
   - [4. Conversation Flow](#4-conversation-flow)
   - [5. Resume Context Auto-injection](#5-resume-context-auto-injection)
   - [6. Session Management](#6-session-management)
5. [Running Both Frontends Locally](#running-both-frontends-locally)
6. [Error Scenarios & Troubleshooting](#error-scenarios--troubleshooting)

---

## Architecture Overview

```
BROWSER / DESKTOP CLIENT
├── HTML SPA (index.html)          gRPC-Web → :8080 (Envoy proxy) → gRPC :50051
│   Auth0 SPA SDK (PKCE flow)
│   Lucide icons · Vanilla JS
│
└── Streamlit (app.py)             gRPC (binary protobuf) → :50051
    No auth required (public RPCs)
    Python grpc channel · st.cache_resource

                    ┌──────────────────────────────────────────┐
                    │         FastAPI / gRPC Backend            │
                    │  ┌─────────────────────────────────────┐ │
                    │  │  LangChain Tool-Calling Agent        │ │
                    │  │  ├─ search_jobs   (SerpAPI)          │ │
                    │  │  ├─ analyze_resume (Gemini LLM)      │ │
                    │  │  └─ generate_cover_letter (Gemini)   │ │
                    │  └─────────────────────────────────────┘ │
                    │  Auth0 RS256 JWT · Langfuse tracing       │
                    └──────────────────────────────────────────┘
```

---

## Frontend Comparison

| Feature | HTML SPA (`index.html`) | Streamlit (`app.py`) |
|---------|------------------------|----------------------|
| Transport | gRPC-Web (via browser) | gRPC binary (via Python) |
| Authentication | Auth0 PKCE (full login or guest) | None (public RPCs only) |
| Resume input | Sidebar textarea | Sidebar textarea |
| Quick actions | 4 toolbar buttons | 4 column buttons |
| Streaming | SSE-capable | Polling (`st.spinner`) |
| Deployment | Vercel (static HTML) | Local only |
| Session ID | Auto-generated UUID | Auto-generated UUID |
| Multi-turn memory | Yes (same session_id) | Yes (same session_id) |

---

## HTML SPA Demo (`index.html`)

### 1. Loading Screen

When the page first loads, a full-screen navy splash screen appears with:
- Animated blue logo (briefcase icon)
- Spinning loader
- Text: "Initialising…"

**What's happening in the background:**
- Auth0 SDK initialising
- Checking for an existing authenticated session
- Backend health check via gRPC-Web

The loading screen dismisses automatically once Auth0 resolves.

---

### 2. Login Screen

After initialisation, the login card is shown if no valid session exists.

**What to demo:**

| Element | Description |
|---------|-------------|
| Logo + title | "Job Placement Agent — Your AI-powered career assistant" |
| Feature list | 4 icons — Find Jobs · Resume Analysis · Cover Letters · Career Advice |
| "Sign in to continue" button | Triggers Auth0 Universal Login (PKCE flow) |
| "Continue as Guest" button | Skips Auth0, enters public (unauthenticated) mode |
| "Secured by Auth0" footer | Reassures users about security |

**Sign in flow:**
1. Click **Sign in to continue**
2. Auth0 Universal Login opens (hosted login page)
3. Enter credentials → Auth0 issues an access token
4. Token stored in memory (SPA SDK handles it)
5. App redirects back → loading screen briefly → main app appears

**What makes this technically interesting:**
- Uses **PKCE (Proof Key for Code Exchange)** — no client secret exposed in the browser
- Token is validated on the backend via **Auth0 JWKS** (RS256 public keys)

---

### 3. Guest Mode

Click **Continue as Guest** to use the app without authentication.

- Guest users hit `/api/chat/public` (or the gRPC `ChatPublic` RPC)
- No JWT token is generated or stored
- All agent features work — job search, resume analysis, cover letters
- A small **GUEST** amber badge is shown in the sidebar user section

**Use case for demo:** Shows the unauthenticated public endpoint; useful when Auth0 credentials are unavailable during a presentation.

---

### 4. Main App Layout

Once authenticated (or guest), the full app layout loads.

```
┌──────────────────┬─────────────────────────────────────────┐
│  SIDEBAR (272px) │  MAIN AREA                              │
│  ───────────     │  ─────────────────────────────────────  │
│  Logo + Brand    │  Chat Header  (Career Chat | Session ID) │
│  User Avatar     │  Quick Actions Bar                      │
│  Status Dot      │                                         │
│  Career Profile  │  Message Feed (scrollable)              │
│   Target Role    │   Welcome card (first load)             │
│   Location       │   User bubbles (navy gradient)          │
│  Resume          │   Agent bubbles (white card)            │
│   Textarea       │   Typing indicator (3 animated dots)    │
│  New Chat btn    │                                         │
│  Retry conn btn  │  Input Area                             │
└──────────────────│   Auto-resize textarea + Send button    │
                   └─────────────────────────────────────────┘
```

**Mobile:** Sidebar collapses off-screen; a hamburger menu button in the header reveals it as an overlay.

---

### 5. Career Profile & Resume Sidebar

The sidebar contains persistent context that the agent uses automatically.

**Career Profile section:**
| Field | Example | Effect |
|-------|---------|--------|
| Target Role | `Data Engineer` | Quick action prompts include this role |
| Preferred Location | `Bangalore` | Job search prompts include this city |

**Resume section:**
- Large textarea for pasting full resume text
- Character count shown below (`1,234 characters`)
- When resume is pasted, quick actions like "Analyse Resume" automatically include the resume text as context

**How to demo:**
1. Paste a sample resume into the sidebar textarea
2. Watch the character counter update
3. Click the "Analyse Resume" quick action — the agent automatically receives the resume text without the user having to type it again

---

### 6. Quick Actions

Four one-click buttons in the toolbar below the chat header:

| Button | Icon | Action |
|--------|------|--------|
| Find Jobs | Search | Builds prompt with target role + location from sidebar |
| Analyse Resume | Bar Chart | Sends resume text + skill gap request |
| Cover Letter | Mail | Generates a tailored cover letter using resume + role |
| Career Tips | Lightbulb | Asks for skills/market insights for the target role |

**Smart prompt building:**
- If **Target Role** and **Location** are filled in, "Find Jobs" sends:
  `"Find me Data Engineer jobs in Bangalore"`
- If not filled, it sends a general prompt asking for details
- If the resume textarea is empty and "Analyse Resume" is clicked, the agent asks the user to share their resume

**What to show the audience:**
1. Fill in "Data Engineer" and "Bangalore" in the sidebar
2. Paste a resume in the sidebar textarea
3. Click **Find Jobs** → agent searches SerpAPI Google Jobs
4. Click **Analyse Resume** → agent analyses the resume, no manual typing needed

---

### 7. Job Search via Chat

**Natural language input:**

Type in the chat input or click the "Find Jobs" quick action.

**Example prompts:**
```
Find me Python developer jobs in Hyderabad
Search for remote machine learning engineer roles
What are the latest backend engineer openings in Pune?
```

**What the agent does:**
1. LCEL intent router classifies intent as `job_search`
2. `search_jobs` tool fires with the extracted query and location
3. SerpAPI Google Jobs API returns real-time listings
4. Gemini formats the response with job titles, companies, locations, and apply links

**Example response in the chat bubble:**
```
Here are the latest Python Developer positions in Hyderabad:

1. **Python Developer** — TCS
   Location: Hyderabad, Telangana
   Skills: Python, Django, REST APIs
   Apply: https://tcs.com/careers/...

2. **Senior Python Engineer** — Infosys
   ...

Would you like me to analyze your resume against any of these roles?
```

**Demo tip:** The response appears in a white rounded card bubble with Markdown rendered — headers, bold text, and bullet points are all styled.

---

### 8. Resume Analysis & Skill Gap

**Step-by-step demo:**

1. Paste this sample resume in the sidebar textarea:

```
Jane Smith | Software Engineer | 3 years
Skills: Python, Django, PostgreSQL, Docker, REST APIs, Git
Experience: Backend Developer @ TechCorp (2021–2024)
  - Built APIs serving 200K daily requests
  - Deployed with Docker on Linux servers
Education: B.E. Computer Science, VIT University (2021)
```

2. Click **Analyse Resume** in the quick actions bar

3. The agent sends a prompt enriched with the resume context automatically

4. The agent responds with:
   - Extracted skills
   - Resume quality score
   - Strengths and improvement areas

**With skill gap detection** — type in chat:
```
Compare my resume against a Senior Data Engineer role
```

The agent:
- Calculates a match percentage
- Shows matched vs missing skills in a table
- Suggests learning paths for each gap

---

### 9. Cover Letter Generation

**Via quick action:**
1. Ensure "Target Role" = `Backend Engineer` and resume is pasted
2. Click **Cover Letter** quick action
3. Agent generates a full cover letter addressed to the company

**Via natural language:**
```
Generate a cover letter for a Senior Backend Engineer role at Zepto
```

**What the output looks like in the bubble:**
```
Jane Smith
jane.smith@email.com

April 19, 2026

Hiring Manager
Zepto Engineering Team

Dear Hiring Manager,

I am writing to express my interest in the Senior Backend Engineer
position at Zepto...
[full professional cover letter]

Warm regards,
Jane Smith
```

The cover letter is rendered as formatted Markdown inside the white assistant bubble, with proper paragraph spacing.

---

### 10. Multi-turn Conversation Memory

The app maintains conversation context across messages within the same session.

**Demo sequence:**
1. Ask: `"What Python skills do I need for a data engineering role?"`
   → Agent lists Spark, Airflow, Kafka, etc.

2. Follow up: `"Great. Now search for data engineering jobs in Pune."`
   → Agent remembers you're targeting data engineering and searches accordingly

3. Follow up: `"Write a cover letter using the first job listed."`
   → Agent uses the previously returned job listing to generate a cover letter

**Technical explanation:** Each message includes the same `session_id` (UUID shown in the session badge in the chat header). The backend's `RunnableWithMessageHistory` injects the full chat history for that session into every Gemini call.

---

### 11. New Conversation & Session Reset

Click **New Conversation** in the sidebar footer.

- Clears the message feed
- Generates a new UUID session ID
- The session badge in the header updates
- Previous conversation context is erased from both the UI and the backend in-memory store

**Use case:** Start fresh between demo scenarios without having to reload the page.

---

### 12. Connection Status Indicator

In the sidebar, a coloured dot shows backend connectivity:

| Dot colour | Status |
|-----------|--------|
| Green (glowing) | gRPC server reachable + healthy |
| Red | Backend unreachable |
| Grey | Connecting / unknown |

The text next to the dot updates to "Connected" or shows the error.

Click **Retry Connection** to re-run the health check without refreshing.

---

### 13. Logout

Click the **log-out icon** button in the sidebar user section (top-right of the user row).

- Calls `auth0Client.logout()`
- Clears the Auth0 session
- Redirects back to the login screen
- Guest users are returned to the login screen without an Auth0 round-trip

---

## Streamlit App Demo (`app.py`)

### 1. Starting the App

**Prerequisites:** Backend gRPC server must be running.

```bash
# Terminal 1 — start gRPC backend
cd src/backend
python main.py
# gRPC server listening on port 50051

# Terminal 2 — start Streamlit frontend
cd src/frontend
pip install -r requirements.txt
streamlit run app.py
# Opens http://localhost:8501
```

**Environment variables (optional):**
```bash
GRPC_HOST=localhost   # default
GRPC_PORT=50051       # default
```

---

### 2. Sidebar — Status & User Info

The Streamlit sidebar (navy background) shows:

| Element | Description |
|---------|-------------|
| 🟢 / 🔴 status | Live gRPC HealthCheck result |
| Full Name | Personalises the welcome message and cover letter prompts |
| Target Role | Pre-fills quick action prompts |
| Preferred Location | Used in job search prompts |
| Resume textarea | Paste resume for analysis and cover letter generation |
| Resume loaded badge | Shows character count when resume is pasted |
| New Chat button | Resets messages + generates new session_id |
| Retry button | Re-probes the gRPC server health |
| Session ID caption | Shows first 8 chars of the UUID |
| Transport caption | Shows `gRPC localhost:50051` |

**What to show:**
1. Open the sidebar — note the navy colour scheme matching the HTML SPA
2. Fill in name, role, and location
3. Paste a resume — the "Resume loaded (X characters)" success badge appears

---

### 3. Quick Action Buttons

Four buttons in a 2×2 grid at the top of the main content area:

| Button | Prompt generated |
|--------|-----------------|
| 🔍 Find Jobs | `"Find me {role} jobs in {city}"` (or generic if fields empty) |
| 📊 Analyse Resume | `"Please analyse my resume [and compare it to {role} requirements]"` |
| ✉️ Cover Letter | `"Generate a cover letter for a {role} position in {city}"` |
| 💡 Career Tips | `"What are the top skills for a {role} in {city}?"` |

Clicking a button sends the generated prompt directly to the `ChatPublic` gRPC RPC and adds the result to the conversation.

---

### 4. Conversation Flow

**Chat display:**
- **User messages:** Navy background, right-aligned rounded bubble
- **Agent responses:** White background with border, left-aligned rounded bubble
- Markdown rendering inside agent bubbles (bold, lists, code blocks)

**Welcome message (empty conversation):**
```
👋 Hello, Jane! I'm your Job Placement Agent.

I can help you:
🔍 Find relevant job listings — just tell me your role and city
📊 Analyse your resume — paste it in the sidebar
🎯 Identify skill gaps — compare your skills to job requirements
✉️  Write cover letters — tailored to any specific job

What would you like to start with?
```

**Chat input:** Standard Streamlit `st.chat_input` at the bottom — press Enter to send.

**Loading state:** `st.spinner("Agent is thinking…")` blocks the UI while the gRPC call is in flight (up to 120 seconds for complex tool calls).

---

### 5. Resume Context Auto-injection

When the user sends a message containing the word "resume" and a resume is pasted in the sidebar, the app automatically appends the resume text to the prompt:

```
User types: "Analyze my resume for a data engineer role"

Actual gRPC message sent:
"Analyze my resume for a data engineer role

[Context — My Resume]:
Jane Smith | Software Engineer | 3 years
Skills: Python, Django, PostgreSQL..."
```

This means users do not need to paste their resume into the chat — it is injected transparently.

---

### 6. Session Management

**Session ID:** Auto-generated UUID, created at app startup.

- Shown in the sidebar as `Session: a3f7b2c1…`
- Sent with every `ChatPublic` RPC call
- Backend maintains conversation history per session_id

**New Chat button:** Resets `st.session_state.messages` to `[]` and generates a new UUID, clearing both local and backend history for the old session.

---

## Running Both Frontends Locally

```bash
# 1. Start FastAPI + gRPC backend
cd src/backend
python main.py        # gRPC on :50051
# OR for REST API:
uvicorn fastapi_app:app --reload --port 8000

# 2. Serve the HTML SPA (option A — Python http.server)
cd src/frontend
python -m http.server 5173

# 2. Serve the HTML SPA (option B — Node/Vite)
cd src/frontend
node build.js
# serves built assets

# 3. Start Streamlit (separate terminal)
cd src/frontend
streamlit run app.py
```

**Environment — `.env` in `src/frontend/`:**
```env
VITE_GRPC_WEB_URL=http://localhost:8080
VITE_AUTH0_DOMAIN=dev-xxxxxx.auth0.com
VITE_AUTH0_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxx
VITE_AUTH0_AUDIENCE=https://job-agent-api
```

---

## Error Scenarios & Troubleshooting

### Backend Offline

**HTML SPA:** Red dot in sidebar. All chat messages result in a toast notification: "Connection failed. Please retry."

**Streamlit:** 🔴 status in sidebar with inline warning:
```
Start the gRPC backend:
cd src/backend
python main.py
(listening on localhost:50051)
```

Sending a message when the backend is offline returns a friendly error in the chat:
```
Could not connect to the gRPC server at localhost:50051.
Please ensure the backend server is running:
  cd src/backend
  python main.py
```

---

### Auth0 Login Failure (HTML SPA)

If Auth0 login fails (wrong credentials, misconfigured tenant), the red error box below the login button shows:

```
Login failed. Please try again or continue as a guest.
```

**Fallback:** Click "Continue as Guest" to use public chat without Auth0.

---

### gRPC Timeout

Long agent operations (SerpAPI + Gemini tool chaining) may exceed the 120-second timeout.

**Streamlit response:**
```
The request timed out. The agent may be processing a complex query.
Please try again or rephrase your question.
```

**Fix:** Rephrase to a simpler request or split into two messages (e.g., search first, then analyse).

---

### Rate Limit (Gemini / SerpAPI)

**Streamlit response:**
```
The AI service is currently rate-limited. Please wait a moment and try again.
```

**HTML SPA:** Error shown as a toast notification with retry guidance.

---

### Resume Too Short

The backend validates that resume text must be **50–50,000 characters**. Pasting a very short snippet will return:

```
The agent couldn't analyse the resume.
Please provide at least a few paragraphs of resume content.
```

**Fix:** Paste the full resume text, not just a summary.

---

### Mobile Layout (HTML SPA)

On screens narrower than 640px:
- Sidebar is hidden by default
- A hamburger menu (☰) button appears in the chat header
- Tap the button to slide the sidebar in as an overlay
- Tap outside the sidebar to dismiss it

---

*HTML SPA deployed to Vercel. Streamlit runs locally only.*  
*gRPC-Web transport (HTML SPA) requires Envoy proxy or Vercel serverless function for production.*  
*For the REST/gRPC API demo guide, see [demo-guide.md](demo-guide.md).*
