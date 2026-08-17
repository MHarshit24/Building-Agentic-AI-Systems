# Problem Statement: Code Mentor – Your AI Pair Programmer

An intelligent coding companion that helps developers understand code, debug issues, improve implementations, and learn best practices through real-time AI assistance.

---


## Context

Developers often face challenges such as debugging errors, understanding unfamiliar code, and applying best practices across different languages and frameworks. Tutorials and documentation exist, but they are often time-consuming to explore during active coding.

**Key Real World Challenges:**  
- Debugging issues consumes significant time and interrupts flow.  
- New developers struggle with advanced coding patterns and APIs.  
- Writing clean, secure, maintainable code requires expert guidance.  
- Searching for solutions online breaks focus.  
- Real-time help is limited in traditional tools.  

## Project Goal

Design an AI-powered Pair Programmer that provides **real-time code explanations, fixes, improvements, and best-practice recommendations** to support developers during development.

Think through what data and context your solution should consider and justify your approach.

---

## Problem Description

This project focuses on building a **Python-based Code Mentor Application** that:

- Understands input code across multiple languages (Python, Java, JavaScript, etc.).  
- Suggests improvements and identifies bugs or inefficiencies.  
- Provides simple explanations of complex logic.  
- Recommends best practices and alternative approaches.  
- Learns the user's coding style over time to personalize guidance.

---

## Functional Requirements

You are free to design how your system works—as long as your solution provides meaningful, context-aware coding assistance.

Your solution might consider:  
- Code input via text or file upload.  
- Detection of syntax errors, logic flaws, or unclear code.  
- Explanations tailored to the user’s experience level.  
- Suggestions for optimized or cleaner code.  
- Reusable snippets, templates, or alternative implementations.  
- User feedback to refine recommendations.  
- AI-generated, context-aware coding insights.

The technical and functional approach is up to you—ensure it aligns with project goals and can be demonstrated in a working prototype.

---

## Technical Details

**Programming Language:** Python

**Libraries & Tools:**

| Library/Tool | Purpose |
|--------------|---------|
| fastapi | Build backend API |
| uvicorn | Run FastAPI server |
| requests | Communicate with Gemini / Ollama APIs |
| dotenv | Manage environment variables securely |

**Environment Variables:**

| Variable | Purpose |
|----------|---------|
| GEMINI_API_KEY | Authenticate requests to Gemini API |
| OLLAMA_MODEL_PATH | Path to local Ollama model instance |

**Note: You may also explore local models and experiment with cloud or private LLM deployments.**

---
