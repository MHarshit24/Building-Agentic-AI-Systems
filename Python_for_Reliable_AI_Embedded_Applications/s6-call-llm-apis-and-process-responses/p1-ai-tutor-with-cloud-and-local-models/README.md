# Study Buddy - A Personalized AI Tutor with LLM Models

This practice is a perfect introduction to **Agentic AI** and **Cloud vs. Local LLMs**. We chain two models to achieve a superior learning outcome: one for facts, one for personalization.

## Problem Statement

Build a Python application that combines cloud (Gemini) and local (phi3:mini via Ollama) LLMs to deliver personalized learning.

Use Gemini for factual explanations and Ollama to transform them into engaging analogies. Implement secure API key management and error handling.

The program must:
- Accept a user query (e.g., "What is RAG?" or "Explain Agentic AI")
- Send it to the cloud model for an accurate explanation
- Forward the same output to the local model for creative rephrasing
- Display both responses in a clean, formatted console output

By completing this practice, you will gain hands-on experience in multi-step agentic workflows, secure API integration, and hybrid AI model design — key skills for building scalable, privacy-aware AI solutions.

## Context

Modern learners are turning to AI-driven platforms for quick explanations and conceptual clarity.

AI tutors typically rely solely on cloud models, raising privacy concerns and delivering generic responses. Build a hybrid solution that uses cloud models for accuracy and local models for personalized, private content generation — keeping sensitive data on the user's machine.

---

## Task Details

### Step 1: Prepare Your Project & Dependencies

Install the required libraries:

```bash
pip install google-genai python-dotenv requests
```

Verify that your environment is properly initialized before proceeding.

### Step 2: Install and Configure Ollama for Local Model Execution

- Download and install [Ollama](https://ollama.com) from its official website.
- Pull the required model using the terminal:

```bash
ollama pull phi3:mini
```

- Start the Ollama service before running the app:

```bash
ollama serve
```

> **Note:** Ollama can be slow on machines with limited RAM/GPU. If it times out, the app will gracefully skip the local step and display a skip message instead of hanging.

### Step 3: Configure Cloud Model Access

Create a `.env` file in your project root (or in the shared `.env` path) with the following:

```dotenv
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=models/gemini-2.0-flash-lite
GEMINI_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/models
```

> **Important:** Use the full model name with the `models/` prefix (e.g., `models/gemini-2.0-flash-lite`). The new `google-genai` SDK requires this format. To see all available models for your API key, run:

```python
for model in client.models.list():
    print(model.name)
```

> **Rate Limits:** The free tier has per-minute and per-day quotas. If you hit a `429 RESOURCE_EXHAUSTED` error, wait for the retry delay shown in the error message, or switch to a different model (e.g., `models/gemini-2.0-flash-lite`, `models/gemini-flash-lite-latest`).

### Step 4: Build and Execute the Tutor Agent

Develop a Python script (`main.py`) that orchestrates both models:

- **Cloud model (Gemini):** for factual, technical explanations
- **Local model (phi3:mini via Ollama):** for creative, private personalization

Accept user queries, process them through both models, and display results in a clear console format.

Run the program:

```bash
python main.py
```

Test with example queries like `"What is RAG?"` or `"Explain Agentic AI"`.

**Hint:** Implement the `get_cloud_explanation_streaming` and `get_local_personalization` functions, plus a `main` loop for user interaction. Use a `timeout` on the Ollama request to avoid hanging:

```python
response = requests.post(url, json=payload, timeout=30)
```

**Prompt for the local model:**
```
f"Rewrite this technical explanation in a highly engaging, fun, and personally 
relatable story or analogy for a beginner student exploring Agentic AI. Be creative 
and do not exceed 4 sentences. The explanation is:\n\n---\n{gemini_explanation}"
```

---

## Example Console Session

```
============================================================
Study Buddy - A Personalized AI Tutor with LLM Models
============================================================
Step 1 (Cloud): Factual Explanation.
Step 2 (Local): Creative Personalization.

Enter an Agentic AI concept (e.g., RAG, LLM, Planning) or 'quit': What is RAG?

--- [1] CLOUD MODEL (Gemini) - Factual Explanation ---

RAG (Retrieval-Augmented Generation) is an architecture that enhances LLMs by
integrating an external knowledge base into the generation process...

--- [2] LOCAL MODEL (phi3 mini) - Private Personalization ---

Imagine you're at a grand library where a robot librarian instantly fetches the
most relevant books before answering your question...

Enter an Agentic AI concept (e.g., RAG, LLM, Planning) or 'quit': quit

Goodbye! Keep learning with AI.
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `404 NOT_FOUND` | Wrong model name format | Use `models/` prefix, e.g. `models/gemini-2.0-flash-lite` |
| `429 RESOURCE_EXHAUSTED` | Free tier quota exhausted | Wait for reset or switch to a different model |
| Ollama request hangs | Model too slow for available hardware | Add `timeout=30` to `requests.post()` or a KeyboardInterrupt exception; the app will skip gracefully |