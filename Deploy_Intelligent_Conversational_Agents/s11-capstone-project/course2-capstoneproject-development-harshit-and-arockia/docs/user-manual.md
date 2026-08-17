# Job Placement Agent — User Manual

**Version:** 1.0.0  
**Last Updated:** April 2026

---

## Table of Contents

1. [What Is the Job Placement Agent?](#1-what-is-the-job-placement-agent)
2. [Getting Started](#2-getting-started)
3. [Chat Interface Guide](#3-chat-interface-guide)
4. [Feature Walkthroughs](#4-feature-walkthroughs)
   - 4.1 [Finding Jobs](#41-finding-jobs)
   - 4.2 [Analyzing Your Resume](#42-analyzing-your-resume)
   - 4.3 [Skill Gap Analysis](#43-skill-gap-analysis)
   - 4.4 [Generating a Cover Letter](#44-generating-a-cover-letter)
   - 4.5 [Full End-to-End Workflow](#45-full-end-to-end-workflow)
5. [Using the REST API Directly](#5-using-the-rest-api-directly)
6. [Authentication (JWT)](#6-authentication-jwt)
7. [Streaming Responses](#7-streaming-responses)
8. [Session Management](#8-session-management)
9. [Troubleshooting](#9-troubleshooting)
10. [FAQ](#10-faq)

---

## 1. What Is the Job Placement Agent?

The **Job Placement Agent** is an AI-powered career assistant that helps you with the complete job application journey — from finding open positions to submitting a polished cover letter.

### What It Can Do

| Capability | How to Ask |
|-----------|-----------|
| **Find Jobs** | "Find Python developer jobs in Austin" |
| **Analyze Resume** | "Here's my resume: [paste text]. What are my top skills?" |
| **Identify Skill Gaps** | "How does my resume compare to this job description?" |
| **Write Cover Letters** | "Write a cover letter for the Google SWE role" |
| **Answer Career Questions** | "What skills should a data scientist have in 2024?" |

### What You'll Need

- A web browser (for the chat UI) or a REST API client (Postman, curl)
- Your resume text (plain text — copy from your resume document)
- Gemini API key, SerpAPI key (pre-configured by your administrator)
- Auth0 credentials (for protected endpoints only)

---

## 2. Getting Started

### Option A — Web Chat Interface

1. Open the application URL in your browser
2. The chat window loads immediately — no login required for the public interface
3. Start typing in the message box at the bottom
4. Press **Enter** or click **Send**

### Option B — REST API

1. Confirm the backend is running:
   ```
   GET https://your-backend.vercel.app/api/health
   ```
   Expected response:
   ```json
   { "success": true, "data": { "status": "healthy", "version": "1.0.0" } }
   ```

2. (Optional) Get an access token for protected endpoints:
   ```
   POST /api/auth/token
   Body: { "username": "your@email.com", "password": "your-password" }
   ```

### Option C — Local Development

```bash
# Start the backend
cd src/backend
uvicorn fastapi_app:app --reload --port 8000

# Open in browser
http://localhost:8000/docs    ← interactive Swagger UI
```

---

## 3. Chat Interface Guide

### Starting a Conversation

The agent is conversational — you can ask naturally, just like messaging a career advisor.

**Good openers:**
- "Hi! I'm looking for a frontend developer job in Chicago."
- "Can you help me with my job search?"
- "I have 5 years of Python experience — what jobs are available?"

### The Agent Remembers Your Context

Once you share information in a session, the agent remembers it:
- If you paste your resume in message 3, you don't need to paste it again in message 7.
- If you mention you're in New York, job searches will default to New York.
- Previous job listings shown to you can be referenced in later messages.

### Session Continuity

Your conversation is tied to a **session ID** (a UUID like `a3f9b2c1-...`). As long as you stay in the same browser tab or pass the same `session_id`, the agent remembers your conversation.

### Ending a Session

Say "Start over" or "Clear my session" to reset the conversation history.

---

## 4. Feature Walkthroughs

### 4.1 Finding Jobs

**What to say:**
```
"Find machine learning engineer jobs in Seattle"
"Show me remote data science roles"
"What Python developer positions are available in London?"
```

**What you'll get:**

The agent calls SerpAPI (Google Jobs) in real-time and returns 5-10 current listings:

```
Here are 8 Machine Learning Engineer jobs I found in Seattle:

1. **Senior ML Engineer** — Amazon
   Remote/Seattle · Posted 2 days ago
   Responsibilities: Build recommendation systems at scale...
   Apply: https://amazon.jobs/...

2. **Machine Learning Engineer II** — Microsoft
   Redmond, WA · Posted 1 week ago
   ...
```

**Pro tips:**
- Be specific: "Find senior React developer jobs at FAANG companies" works better than "find jobs"
- Add location for better results: role + city + country
- Ask for more: "Show me 5 more" or "Find jobs with higher salaries"

---

### 4.2 Analyzing Your Resume

**What to say:**
```
"Analyze my resume"
"What skills do I have?"
"Review my resume and give me feedback"
```

Then paste your resume text when prompted (or include it in the same message):

```
Analyze this resume:

John Smith
Software Engineer | john@example.com

EXPERIENCE
Senior Python Developer, Startup Inc. (2020–2024)
  - Built FastAPI microservices serving 100k daily users
  - Led migration from monolith to Kubernetes-based microservices
  - Mentored 3 junior developers

SKILLS
Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis, AWS, Git
```

**What you'll receive:**

```
## Resume Analysis

### Extracted Skills
**Technical:** Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis, AWS, Git
**Soft Skills:** Leadership, Mentoring, Technical Communication

### Experience Assessment
- **Years:** ~4 years
- **Level:** Senior / Lead Engineer
- **Progression:** Individual contributor → Tech lead

### Resume Quality Score: 7.8 / 10

**Strengths:**
- Concrete metrics (100k daily users)
- Modern cloud-native stack
- Leadership experience

### Top 3 Improvements
1. Add links to GitHub projects or portfolio
2. Quantify more achievements (performance improvements, cost savings)
3. Add a brief professional summary at the top
```

---

### 4.3 Skill Gap Analysis

This is the most powerful feature — compare your resume against a specific job description.

**Step 1:** Paste your resume
**Step 2:** Paste the job description

```
Here's my resume: [paste resume]

And here's the job I want to apply for:

We are looking for a Senior Data Scientist with:
- 5+ years of machine learning experience
- Strong Python and R programming skills
- Experience with MLOps (MLflow, Kubeflow, or similar)
- Deep learning frameworks: PyTorch or TensorFlow
- Data pipeline tools: Airflow, Spark
- Communication skills to present to non-technical stakeholders

How do I compare?
```

**What you'll receive:**

```
## Skill Gap Analysis

### Your Strengths (Present in both):
✅ Python programming
✅ Machine learning experience (4 years)
✅ Strong communication skills

### Missing Skills:
❌ R programming
❌ MLOps tools (MLflow, Kubeflow)
❌ Deep learning frameworks (PyTorch/TensorFlow)
❌ Data pipeline tools (Airflow, Spark)

### Match Percentage: 45%

### Priority Skills to Develop:
1. **PyTorch** — highest demand, 3-4 week ramp-up recommended
2. **MLflow** — experiment tracking, relatively quick to learn
3. **Apache Spark** — useful for large-scale data; focus on PySpark

### Verdict:
You're a strong Python ML practitioner. With 2-3 months of focused
upskilling on the missing tools, you'd be a competitive applicant.
```

---

### 4.4 Generating a Cover Letter

**What to say:**
```
"Write me a cover letter for this role"
"Generate a cover letter for the Google data scientist position"
"Create a cover letter — I'm Jane Doe applying for Senior Engineer at Stripe"
```

The agent needs four pieces of information:
1. Your name
2. Job title
3. Company name
4. Job description

If any are missing, the agent will ask for them.

**Example exchange:**

```
You:    Write a cover letter for the Stripe Senior Engineer role.
Agent:  I'd love to help! Could you share the job description and
        confirm your name?
You:    My name is Jane Doe. Here's the JD: [paste JD]
Agent:  [generates personalized cover letter]
```

**Sample output:**

```
Dear Hiring Manager,

I am writing to express my strong interest in the Senior Software
Engineer position at Stripe. With over 6 years of experience building
high-performance payment infrastructure and distributed systems, I am
excited by the opportunity to contribute to Stripe's mission of
increasing the GDP of the internet.

In my current role at Startup Inc., I led the migration of our payment
processing pipeline to a microservices architecture, reducing latency
by 40% and improving reliability to 99.99% uptime. This directly aligns
with Stripe's focus on reliability and developer experience.

[... continues for ~350 words ...]

I would welcome the opportunity to discuss how my background aligns
with Stripe's engineering challenges.

Sincerely,
Jane Doe
```

**Refining the letter:**
- "Make it shorter — 200 words max"
- "Use a more formal tone"
- "Emphasize my leadership experience more"
- "Add a paragraph about my AWS expertise"

---

### 4.5 Full End-to-End Workflow

Here's a complete job application session from start to finish:

```
── Step 1: Find jobs ──────────────────────────────────────────────────────
You:   Hi! I'm Sarah, a data engineer with 4 years experience.
       Find me data engineering jobs in Chicago.

Agent: Here are 7 Data Engineering positions in Chicago:
       1. Senior Data Engineer — JPMorgan Chase · $140-160k
       2. Data Platform Engineer — Grubhub · $120-140k
       ...

── Step 2: Analyze your resume ────────────────────────────────────────────
You:   Here's my resume: [paste 500-word resume]
       How do I stack up against the JPMorgan role?

Agent: ## Skill Gap Analysis for JPMorgan Senior Data Engineer

       Matching skills (8): Python, SQL, Spark, Airflow, AWS, dbt,
                            Kafka, data modeling
       Missing skills (3): Scala, Databricks, Terraform

       Match Score: 72% — You're a strong candidate!

── Step 3: Generate a cover letter ────────────────────────────────────────
You:   Write a cover letter for the JPMorgan role.

Agent: Dear Hiring Manager,

       I am excited to apply for the Senior Data Engineer position at
       JPMorgan Chase. My 4 years of experience building enterprise
       data pipelines with Python, Apache Spark, and AWS makes me
       well-positioned to contribute to JPMorgan's data infrastructure...

── Step 4: Refine ─────────────────────────────────────────────────────────
You:   Can you make it more concise? Also mention my SQL optimization
       project that cut query time by 60%.

Agent: [revised cover letter, ~250 words, includes SQL optimization detail]
```

---

## 5. Using the REST API Directly

### Postman / curl Quick Reference

**Health check:**
```bash
curl https://your-backend.vercel.app/api/health
```

**Chat (public — no auth):**
```bash
curl -X POST https://your-backend.vercel.app/api/chat/public \
  -H "Content-Type: application/json" \
  -d '{"message": "Find Python jobs in NYC", "session_id": "my-session-1"}'
```

**Get access token:**
```bash
curl -X POST https://your-backend.vercel.app/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "you@email.com", "password": "your-password"}'
```

**Authenticated chat:**
```bash
curl -X POST https://your-backend.vercel.app/api/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Analyze my resume", "session_id": "my-session-1"}'
```

**Direct job search:**
```bash
curl -X POST https://your-backend.vercel.app/api/jobs/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Machine Learning Engineer", "location": "Remote"}'
```

**Direct resume analysis:**
```bash
curl -X POST https://your-backend.vercel.app/api/resume/analyze \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "John Smith, Software Engineer...",
    "job_description": "We are looking for..."
  }'
```

**Direct cover letter:**
```bash
curl -X POST https://your-backend.vercel.app/api/cover-letter/gen \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "...",
    "job_title": "Senior Engineer",
    "company_name": "Acme Corp",
    "job_description": "...",
    "user_name": "Your Name"
  }'
```

**Interactive API docs (Swagger UI):**
```
https://your-backend.vercel.app/docs
```

---

## 6. Authentication (JWT)

### Who Needs Authentication?

| Endpoint | Auth Required? |
|----------|---------------|
| `GET /api/health` | No |
| `POST /api/auth/token` | No |
| `POST /api/chat/public` | No |
| `POST /api/session` | No |
| `POST /api/chat/stream` | No |
| `POST /api/chat/route` | No |
| `POST /api/chat` | **Yes** |
| `POST /api/chat/async` | **Yes** |
| `POST /api/jobs/search` | **Yes** |
| `POST /api/resume/analyze` | **Yes** |
| `POST /api/cover-letter/gen` | **Yes** |
| `DELETE /api/chat/{id}` | **Yes** |
| `GET /api/sessions` | **Yes** |

### Getting a Token

```bash
POST /api/auth/token
{
  "username": "your-email@example.com",
  "password": "your-auth0-password"
}

Response:
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiJ9...",
    "token_type": "Bearer",
    "expires_in": 86400
  }
}
```

### Using the Token

Add the header to every protected request:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiJ9...
```

Tokens expire after **24 hours**. Request a new one from `/api/auth/token`.

### Token Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 AUTH0_INVALID_CREDENTIALS` | Token expired or invalid | Get a new token |
| `503 AUTH0_UNAVAILABLE` | Auth0 is unreachable | Retry in a few minutes |
| `500 AUTH0_CONFIGURATION_ERROR` | Server misconfiguration | Contact your admin |

---

## 7. Streaming Responses

The `/api/chat/stream` endpoint delivers the agent's response word-by-word using **Server-Sent Events (SSE)**. This is ideal for building chat UIs that show text appearing progressively.

### JavaScript Example

```javascript
const response = await fetch('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Find me Python jobs', session_id: 'my-sess' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value);
  const lines = buffer.split('\n\n');
  buffer = lines.pop();   // keep incomplete line

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    const data = JSON.parse(line.slice(6));

    if (data.done) {
      console.log('Stream complete');
    } else if (data.error) {
      console.error('Stream error:', data.message);
    } else {
      process.stdout.write(data.token);   // append token to UI
    }
  }
}
```

### Python Example

```python
import requests, json

with requests.post(
    'http://localhost:8000/api/chat/stream',
    json={'message': 'Analyze my resume', 'session_id': 'sess-1'},
    stream=True
) as resp:
    for line in resp.iter_lines():
        if line and line.startswith(b'data: '):
            data = json.loads(line[6:])
            if data.get('done'):
                break
            elif data.get('error'):
                print('Error:', data['message'])
                break
            else:
                print(data['token'], end='', flush=True)
```

### SSE Event Formats

| Event | JSON format |
|-------|------------|
| Token | `{"token": "Hello", "session_id": "uuid"}` |
| Done | `{"done": true, "session_id": "uuid"}` |
| Error | `{"error": "STREAM_ERROR", "message": "..."}` |

---

## 8. Session Management

### Creating a Session

```
POST /api/session
Response: { "data": { "session_id": "a3f9b2c1-...", "message": "Session created." } }
```

### Using a Session

Pass the `session_id` in every request to maintain conversation context:

```json
{ "message": "Now write a cover letter", "session_id": "a3f9b2c1-..." }
```

### Clearing a Session

```
DELETE /api/chat/a3f9b2c1-...
Response: { "data": { "message": "Session cleared successfully.", "session_id": "a3f9b2c1-..." } }
```

### Listing Sessions

```
GET /api/sessions    (requires JWT)
Response: { "data": { "sessions": ["a3f9b2c1-...", "b7e3d4f2-..."] } }
```

### Session Limits

- Sessions are stored in memory — they reset when the server restarts
- There is no hard session count limit, but idle sessions are not automatically expired
- Clear sessions you no longer need to free memory

---

## 9. Troubleshooting

### The agent is not finding jobs

**Possible causes:**
- SerpAPI key not configured or quota exceeded
- Very specific query with no results

**Try:**
- Broaden your search: "Python developer jobs" instead of "Python developer at Google in San Francisco"
- Check with your administrator that the SerpAPI key is valid
- Look for `429 JOB_SEARCH_RATE_LIMITED` in the response

---

### Resume analysis returns an error

**Possible causes:**
- Resume text too short (minimum 50 characters)
- Gemini API key expired or rate limited

**Try:**
- Make sure you've pasted the full resume text, not just your name
- If you see `429 LLM_RATE_LIMITED`, wait 60 seconds and try again
- Check the error `code` field in the response JSON

---

### I get a 401 error

**Cause:** Your JWT token has expired (tokens last 24 hours) or is invalid.

**Fix:**
```bash
POST /api/auth/token
{ "username": "...", "password": "..." }
```
Use the new `access_token` in your next requests.

---

### The cover letter is too generic

The agent needs specific context. Include:
- Your actual name
- The full job description (not just the job title)
- Key achievements from your resume

**Example:**
```
Write a cover letter for this role as John Smith.
Here's my background: [full resume]
Here's the job: [full job description]
Please emphasize my experience scaling Python services to 1M users.
```

---

### Responses are slow

**Expected response times:**
- Job search: 3-8 seconds (SerpAPI network call)
- Resume analysis: 5-15 seconds (LLM generation)
- Cover letter: 10-20 seconds (longer generation)
- Multi-step workflows: 15-30 seconds

Use `/api/chat/stream` to see tokens appearing progressively while waiting for the full response.

---

### The streaming endpoint is not showing tokens

The SSE endpoint requires the client to handle `text/event-stream`. Make sure:
1. You are **not** buffering the full response before processing
2. Each `data:` line ends with two newlines (`\n\n`)
3. Your proxy/load balancer is not buffering responses (check `X-Accel-Buffering: no` header)

---

## 10. FAQ

**Q: Do I need an account to use the agent?**  
A: The public chat endpoint (`/api/chat/public`) requires no authentication. Protected endpoints (direct job search, resume analysis, cover letter generation, session management) require an Auth0 JWT token.

---

**Q: Is my resume data stored anywhere?**  
A: Resume text is processed in-memory during the conversation and is not persisted to a database. Session history is stored in process memory and is cleared when the server restarts or when you call `DELETE /api/chat/{session_id}`.

---

**Q: How accurate are the job listings?**  
A: Job listings come directly from SerpAPI's Google Jobs integration in real time. They reflect what's available on Google Jobs at the time of your search. Some listings may be outdated — always verify on the employer's official site before applying.

---

**Q: Can I use this for multiple job applications simultaneously?**  
A: Yes. Use a different `session_id` for each job target to keep context separate:
- `session-google-swe` for your Google application
- `session-stripe-eng` for your Stripe application

---

**Q: How do I integrate this with my own application?**  
A: Use the REST API. The API follows standard JSON REST conventions with an `ApiResponse` envelope. See [Section 5](#5-using-the-rest-api-directly) and the interactive docs at `/docs`.

---

**Q: The agent mentioned Langfuse — what is that?**  
A: Langfuse is an observability tool used by developers to monitor LLM calls, track latency, and debug issues. As a user, you don't interact with it directly — it runs transparently in the background. If it's not configured, the agent works exactly the same.

---

**Q: Can the agent help me with interview preparation?**  
A: While the agent focuses on job search, resume, and cover letters, you can ask it general career questions. It won't run a mock interview, but it can answer questions like "What technical questions are asked for Senior Python Engineer roles?"

---

**Q: How do I reset the conversation without creating a new session?**  
A: Call `DELETE /api/chat/{session_id}` to clear the history, then resume chatting with the same `session_id`. The agent will have no memory of the previous conversation.

---

**Q: What if I make a typo or give wrong information?**  
A: Just correct it in your next message — "Actually, I have 6 years of experience, not 4" — and the agent will update its understanding for the rest of the session.

---

*For technical issues or API errors, check the `error.code` field in the response JSON and refer to [Section 9 Troubleshooting](#9-troubleshooting).*
