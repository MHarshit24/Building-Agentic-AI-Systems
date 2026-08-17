# Course: Build Production-Grade RAG Systems

## Capstone Project Overview

This capstone project gives you a hands-on opportunity to apply everything learned across the course. By selecting one of the provided project scenarios, you will design and build a **Production-Grade Retrieval-Augmented Generation (RAG) System** using modern AI engineering practices.

Your goal is to architect, develop, evaluate, and present a fully functional **RAG-powered backend application** that integrates unstructured document retrieval, structured data access, external system integration, safety guardrails, evaluation against SLOs, and human-in-the-loop workflows.

This project simulates real-world development of **enterprise RAG systems**—designed to handle complex documents, multiple data sources, reliability constraints, and production readiness requirements.

---

### Your Task

**[Priority High]**

1. Select one of the provided **project scenarios** (e.g., document intelligence system, research assistant, enterprise knowledge assistant, domain-specific RAG system, etc.).
2. Design the **system architecture** (ingestion pipelines, indexing strategy, retrieval flow, query routing, evaluation, and handoff).
3. Build a **RAG-powered backend application** that implements:
   - Document ingestion and preprocessing pipelines  
   - Vector-based retrieval using a vector database  
   - **RAG pipelines using LangChain or LlamaIndex** (as per assigned project)  
   - **Structured data access using SQL**  
   - **Intelligent query routing** (unstructured, structured, hybrid)  
   - **External system integration** using Model Context Protocol (MCP)  
   - **Safety guardrails** and response validation  
   - **Evaluation against Service Level Objectives (SLOs)**  
   - **Human handoff with full context transfer**
4. Add **observability and evaluation tooling** to analyze retrieval quality and system behavior.
5. Implement clean **error handling**, modular architecture, and production-oriented code.

**[Priority Low]**

Create a minimal frontend:
- Build a simple UI to interact with the RAG system.

**[Priority High]**

Prepare a **final project presentation and live demo**.

---

## Project Objectives

By completing this project, you will:

- Design and build a modular, scalable **production-grade RAG system**.
- Implement robust **document ingestion, indexing, and retrieval pipelines**.
- Combine **unstructured retrieval (RAG)** with **structured SQL-based lookups**.
- Apply **intelligent query routing** strategies.
- Integrate **external tools and systems** using MCP.
- Implement **guardrails** for safety and reliability.
- Evaluate system performance using **SLO-driven metrics**.
- Support **human-in-the-loop workflows** for complex queries.
- Present your end-to-end solution professionally.

---

## Project Workflow and Milestones

### 1. Requirement Analysis & Planning
- Select your project scenario.
- Define query types and user flows.
- Identify unstructured documents, structured data, and external systems.
- Submit a one-page architecture plan.

### 2. Environment Setup
- Create backend project structure.
- Configure environment variables and secrets.
- Set up vector database and SQL database.
- Install core dependencies required for RAG development.

### 3. Core RAG Pipeline Development
- Implement document ingestion and indexing.
- Build retrieval and RAG pipelines.
- Expose query APIs.

### 4. Query Routing & Data Integration
- Implement routing between RAG, SQL, and hybrid flows.
- Integrate structured data sources.
- Combine results where applicable.

### 5. External System Integration
- Integrate external tools or APIs using MCP.
- Handle failures and partial responses gracefully.

### 6. Safety & Guardrails
- Implement validation and safety mechanisms.
- Add fallback and uncertainty handling logic.

### 7. Evaluation & SLOs
- Define evaluation metrics.
- Measure accuracy, latency, and response quality.
- Analyze and document evaluation results.

### 8. Human Handoff
- Enable escalation for complex or ambiguous queries.
- Transfer full system context for human review.

### 9. Documentation & Presentation
- Create README and architecture diagrams.
- Prepare a 3–4 minute live demo.

---

## Deliverables & Sprint Timeline

| Sprint # | Deliverable | Description |
|---------|------------|-------------|
| **Sprint 11** | **Project Approach Document** | Problem definition, objectives, selected scenario, data sources, and overall RAG system architecture including ingestion, retrieval, query routing, evaluation, and human handoff strategy. |
| **Sprint 11** | **Backend & Infrastructure Setup** | Project structure, dependency setup, environment configuration, vector database, SQL database, and foundational infrastructure required to run the RAG system. |
| **Sprint 12** | **Core RAG Implementation** | Document ingestion, indexing, retrieval pipelines, query APIs, structured data integration, query routing logic, and external system integration where applicable. |
| **Sprint 12** | **Safety & Evaluation Setup** | Guardrails implementation, validation logic, and evaluation of the RAG system against defined SLOs. |
| **Sprint 14 / 15** | **Final Demo & Documentation** | Final project presentation, live demo, complete documentation including README, architecture diagrams, workflow explanation, and evaluation results. |

---

## Guidelines for Success

- Start early and build incrementally.
- Prioritize correctness, reliability, and explainability over complexity.
- Write clean, modular, production-oriented code.
- Clearly justify retrieval and routing decisions.
- Validate responses and handle failure cases gracefully.
- Maintain clear and structured commit history.

---

## Evaluation Criteria

| Parameter | Weight |
|----------|--------|
| Architecture & System Design | 13% |
| RAG Pipeline Implementation | 28% |
| Query Routing & Data Integration | 18% |
| Safety & Reliability | 18% |
| Documentation & Presentation | 10% |
| Creativity & Enhancements | 13% |

**Total: 100%**

---

## Project Scenario Options

Choose from any of the provided **Course-3 RAG scenarios**.
- [MedLearn Assistant](MedLearn%20Assistant) 
- [LegalDoc Navigator](LegalDoc%20Navigator)  
- [ResearchHub](ResearchHub)  
- [TechDocs Pro](TechDocs%20Pro)  
- [CodebaseGPT](Codebase%20Intelligence%20&%20Documentation%20System)

Each scenario includes:
- Problem statement  
- Functional requirements  
- Data sources  
- Technical expectations  

---

## Conclusion

This capstone project helps you apply your knowledge to build a **real, production-grade RAG system** with essential AI engineering components:

- Document ingestion  
- Retrieval-Augmented Generation  
- Structured data integration  
- External system access  
- Guardrails  
- Evaluation  
- Human handoff  

By completing this project, you’ll have a **portfolio-ready RAG system**, demonstrating your ability to design and implement **reliable, evaluated, and production-aligned AI systems** end to end.
