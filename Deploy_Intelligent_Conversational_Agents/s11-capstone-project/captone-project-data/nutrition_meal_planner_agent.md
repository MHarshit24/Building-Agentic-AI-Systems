# Personalized Nutrition & Meal Planner Agent – Your AI-Powered Health & Diet Companion

An intelligent conversational agent that helps users analyze nutritional content, plan healthy meals, manage dietary restrictions, and create personalized diet plans based on goals, preferences, and lifestyle—powered by real-time nutrition and recipe APIs.

---

## Problem Statement: Personalized Nutrition & Meal Planner Agent

### Context

In today’s fast-paced world, people increasingly want to improve their health but struggle with the complexity of nutrition. They must manually track calories, identify nutrient breakdowns, plan weekly meals, and manage allergies or food intolerances. Without expert guidance, making healthy decisions becomes overwhelming and unsustainable.

**Common Challenges:**

- **Lack of Nutrition Awareness:** Most individuals cannot accurately estimate calories or nutrient content of their meals.  
- **Meal Planning Difficulty:** Creating balanced daily or weekly meal plans feels time-consuming and complicated.  
- **Dietary Restrictions:** Managing allergies, food intolerance, or specific diets (keto, vegan, diabetic-friendly) is difficult without tools.  
- **Finding Healthy Alternatives:** People struggle to find nutritious substitutes or recipe options that match their goals.  
- **Scattered Information Sources:** Nutrition facts, recipes, and diet advice are spread across multiple apps.  
- **No Context Awareness:** Standard nutrition apps do not remember user preferences across a session.

### Project Goal

Build an **AI-powered Personalized Nutrition & Meal Planner Agent** that provides a conversational interface to analyze food, track nutrition, recommend healthy meals, and generate personalized meal plans—while understanding allergies, goals, and preferences.

---

## Problem Description

This project focuses on building a **full-stack Nutrition Assistant Application** that:

- Conversationally interacts with users to understand diet goals, allergies, calorie targets, and preferred cuisines.  
- Uses **external APIs for real-time nutrition analysis and recipe search** (**Note: The APIs mentioned below are suggestions. You are free to use other nutrition/recipe APIs that suit your needs**):
  - **Edamam Recipe Search API (Free Tier)** — provides healthy recipe options, ingredients, calories, cooking instructions, and nutritional data.  
    API URL: https://developer.edamam.com/edamam-recipe-api  
  - **Nutritionix API (Free Tier)** — provides nutritional breakdown of meals, packaged foods, fast foods, and custom user-entered items.  
    API URL: https://developer.nutritionix.com/

**Disclaimer: The API key generation link provided may be subject to a paid version. You have full discretion to switch to an alternative API key or plan based on your project requirements.**
 
- Generates personalized daily and weekly meal plans based on user's calorie targets.  
- Analyzes nutritional value of meals including calories, macros, and micronutrients.  
- Offers food substitutions, lifestyle tips, and grocery lists.  
- Maintains short-term session memory including allergies, calorie targets, past meals, and previous meal plans.  
- Provides observability using Langfuse for reasoning steps, API calls, and decision workflows.

---

## Functional Requirements

### 1. Conversational Health Assistant

The agent should:
- Understand user's dietary goals (weight loss, muscle gain, diabetes management, etc.)  
- Ask clarifying questions about lifestyle, restrictions, and meals  
- Interpret ingredients, dish names, or meal descriptions  
- Maintain conversation context throughout the session  

### 2. Real-Time Nutrition API Integrations

You can use the suggested APIs below or choose alternative nutrition/recipe APIs that better fit your project needs.

#### **A. Edamam Recipe Search API **
Used for:
- Searching recipes based on preferences  
- Getting ingredients, calories, macros  
- Providing healthy substitutions  
- Delivering cooking instructions  

#### **B. Nutritionix API **
Used for:
- Nutrient breakdown of user-entered meals  
- Branded food nutrition (restaurants, packaged items)  
- Calorie tracking  

The agent should automatically decide which API to call depending on user input:
- Meal description → Nutritionix  
- Recipe suggestions → Edamam  

### 3. Nutritional Breakdown

Provide:
- Total calories  
- Protein, carbs, and fat  
- Vitamin & mineral breakdown  
- Health labels (vegan, gluten-free, keto, etc.)  

### 4. Personalized Meal Plans

Should generate:
- Daily or weekly plans  
- Multiple variations based on allergies, preferences, and goals  
- Portion size recommendations  
- Balanced combinations of breakfast, lunch, dinner, and snacks  

### 5. Dietary Recommendations

Provide:
- Smart food substitutions  
- Grocery list generation  
- Healthy lifestyle tips based on goals  
- Hydration, sleep, and activity suggestions  

### 6. Multi-Step Workflow Implementation

Examples:
- User describes a meal → Agent calls Nutritionix → Returns breakdown → Suggests alternatives  
- User wants a weekly plan → Collect preferences → Fetch recipes via Edamam → Generate structured plan  
- User enters allergies → Filter all recipe suggestions accordingly  

### 7. Short-Term Session Memory

Remember:
- Allergies  
- Calorie target  
- Preferred cuisines  
- Meals already planned  
- Dietary restrictions  

Memory resets after session ends.

### 8. LangChain Backend

Backend responsibilities:
- Secure endpoints (if authentication is implemented)  
- Host LangChain agent pipeline  
- Implement external API integrations (Nutritionix, Edamam, or alternatives)  
- Session memory handling  
- Langfuse logging for observability  

### 9. Observability with Langfuse

Track:
- LLM outputs  
- API calls  
- Workflow steps  
- Latency & errors 

### 10. Secure Authentication with Auth0 

**Note:** Authentication is optional. If implemented:
- User must log in to use the planner  
- The frontend must obtain a JWT and pass it to the FastAPI backend.(Optional)
- The FastAPI backend must validate the JWT before processing agent requests.(Mandatory)

### 11. Frontend (Streamlit/React/HTML,CSS,JavaScript)(Optional)

**Note:** Frontend design is optional. If implemented, consider including:
- Login/logout via Auth0 (if authentication is implemented)  
- Chat-based nutrition assistant  
- Meal plan visualization  
- Nutrition breakdown cards  
- Recipe suggestions viewer  
- Grocery list generator  

 

---

## Technical Details

**Languages:** Python (Backend), TypeScript/JavaScript (Frontend)

### Libraries & Tools

| Tool | Purpose |
|------|---------|
| `fastapi` | Backend API |
| `uvicorn` | Server |
| `langchain` | Agent pipeline |
| `requests` | External API calls |
| `langfuse` | Observability |
| `python-jose` | JWT validation |
| `python-dotenv` | Env variables |
| `react` | Frontend |
| `vite` | The Build Tool for the Web |
| `Streamlit` | Faster way to build and share Data Apps |
| `auth0-react` | Authentication |

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
2. External API Integration (Required - can use Edamam/Nutritionix or alternative APIs)
3. Langfuse Observability (Required)
4. Frontend Application (React/Streamlit/HTML,CSS,JavaScript or any UI implementation in the project)
5. Auth0 Authentication (Backend required)
6. README with setup, workflows, diagrams, and screenshots  

---

## Goal

Build a production-ready intelligent nutrition assistant that blends LLM reasoning, food analysis, recipe search, meal planning, authentication, observability, and a modern UX—similar to cutting-edge health & fitness AI apps.

