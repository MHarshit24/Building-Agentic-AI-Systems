# Personal Finance & Budget Advisor Agent – Your AI-Powered Money Management Companion

An intelligent conversational agent that analyzes spending patterns, categorizes expenses, provides personalized budgeting recommendations, helps set savings goals, and offers financial insights—powered by real-time currency and geolocation data.

---

## Problem Statement: Personal Finance & Budget Advisor Agent

### Context

Managing personal finances is one of the most common yet challenging tasks for individuals. Most people lack visibility into how they spend their money and struggle to categorize expenses, forecast future spending, and stay consistent with savings goals. Traditional budgeting tools often feel rigid, overwhelming, or disconnected from day-to-day financial behavior.

**Common Challenges:**

- **Poor Spending Visibility:** Users lack clarity on where their money is going each month.  
- **Manual Categorization:** Tracking and tagging expenses by category is time-consuming.  
- **Generic Advice:** Budgeting apps offer static recommendations rather than personalized insights.  
- **No Forecasting:** People have trouble predicting upcoming expenses or future financial health.  
- **Savings Struggles:** Users find it hard to set and follow realistic savings goals.  
- **Lack of Context Awareness:** Finance apps don’t remember user habits, income, or past insights within a session.

### Project Goal

Build an **AI-powered Personal Finance & Budget Advisor Agent** that provides a conversational interface to analyze spending, categorize transactions, generate budget recommendations, and create goal-based savings plans—while maintaining financial context during the session.

---

## Problem Description

This project focuses on building a **full-stack Finance Advisor Application** that:

- Conversationally gathers user income, expenses, categories, and financial goals.  
- Accepts both itemized transactions and monthly spending summaries.  
- Uses **external APIs for enhanced financial intelligence** **(Note: The APIs mentioned below are suggestions. You are free to use other financial/geolocation APIs that suit your needs):**
  - **ExchangeRate API (Free, No Key Required)** — provides real-time currency exchange rates for converting expenses or income across currencies for users dealing with international spending.  
    API URL: https://www.exchangerate-api.com/  
  - **Open-Meteo Geolocation API (Free, No Key Required)** — assists in inferring regional context or cost-of-living approximations using user geolocation (optional).  
    API URL: https://open-meteo.com/

**Disclaimer: The API key generation link provided may be subject to a paid version. You have full discretion to switch to an alternative API key or plan based on your project requirements.**

- Categorizes expenses using LLM reasoning + rule-based heuristics.  
- Generates weekly and monthly spending insights with breakdowns.  
- Provides personalized budgeting recommendations and alerts for overspending.  
- Helps users set savings goals and track progress.  
- Maintains short-term session memory: income, categories, goals, spending patterns.  
- Includes Langfuse observability for tracking agent behavior, reasoning, and API/tool usage.

---

## Functional Requirements

### 1. Conversational Finance Assistant

The agent must:
- Understand income, recurring expenses, lifestyle costs, and one-time transactions  
- Ask clarifying questions about ambiguous entries  
- Accept lists of transactions or individual spending items  
- Maintain financial context throughout the session  

### 2. Real-Time External API Integrations

You can use the suggested APIs below or choose alternative financial/geolocation APIs that better fit your project needs.

#### **A. ExchangeRate API (Suggested - Free, No Key Needed)**  
Used for:
- Converting foreign transaction amounts to user's currency  
- Understanding fluctuations in conversion rates  
- Global spending insights  

#### **B. Open-Meteo Geolocation API (Suggested - Free, No Key Needed)**  
Used for:
- Inferring user region for spending comparisons  
- Cost-of-living–based recommendations  
- Location-specific alerts (optional)  

The agent must intelligently determine when currency conversion or geolocation context is needed.

### 3. Expense Categorization & Insights

Provide:
- Categorized spending across food, rent, utilities, shopping, entertainment, etc.  
- Weekly and monthly breakdowns  
- Overspending alerts  
- Trend analysis and pattern detection  

### 4. Personalized Budget Recommendations

Offer:
- Suggested category-wise budget allocations  
- Savings recommendations based on goals and lifestyle  
- Alerts for unusual or unexpected expenses  
- Behavioral insights based on spending history  

### 5. Goal-Based Financial Planning

Support:
- Custom savings goals (travel, emergency fund, major purchase)  
- Financial timelines and progress estimates  
- Suggestions for achieving targets faster  

### 6. Multi-Step Workflow Implementation

Examples:
- User uploads monthly expenses → Agent categorizes → Generates insights → Suggests budgets  
- User enters spending goals → Agent calculates savings rate → Builds a monthly plan  
- User logs foreign transactions → Agent converts via ExchangeRate API → Updates spending breakdown  

### 7. Short-Term Session Memory

Remember during the session:
- Income level  
- Savings goals  
- Spending categories  
- Recent spending summaries  
- Lifestyle preferences  

Memory resets after session ends.

### 8. LangChain Backend

Backend should:
- Expose secure endpoints for financial analysis (if authentication is implemented)  
- Host the LangChain-powered agent  
- Handle API integrations with ExchangeRate + Open-Meteo (or alternative APIs)  
- Implement memory and conversation flow logic  
- Log traces to Langfuse  

### 9. Observability with Langfuse

Monitor:
- Reasoning steps  
- Tool and API calls  
- Workflow paths  
- Errors, retries, latency  

### 10. Secure Authentication with Auth0

**Note:** Authentication is optional. If implemented:
- Require login before accessing agent features  
- The frontend must obtain a JWT and pass it to the FastAPI backend.(Optional)
- The FastAPI backend must validate the JWT before processing agent requests.(Mandatory)  

### 11. React Frontend (Optional)

**Note:** Frontend design is optional. If implemented, consider including:
- Login/logout via Auth0 (if authentication is implemented)  
- Chat interface with the finance agent  
- Transaction entry interface  
- Category-wise charts and breakdowns  
- Budget recommendation panels  
- Goal progress tracker  



---

## Technical Details

**Languages:** Python (Backend), TypeScript/JavaScript (Frontend)

### Libraries & Tools

| Tool | Purpose |
|------|---------|
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
2. External API Integration (Required - can use ExchangeRate/Open-Meteo or alternative APIs)
3. Langfuse Observability (Required)
4. React Frontend Application (React/Streamlit/HTML,CSS,JavaScript or any UI implementation in the project)
5. Auth0 Authentication (Backend required)
6. README with setup steps, diagrams, workflows, and screenshots  

---

## Goal

Build a production-grade intelligent personal finance assistant that combines LLM reasoning, financial analysis, categorization, currency conversion, savings planning, workflow orchestration, authentication, and modern UI/UX—similar to cutting-edge financial advisory AI tools.

