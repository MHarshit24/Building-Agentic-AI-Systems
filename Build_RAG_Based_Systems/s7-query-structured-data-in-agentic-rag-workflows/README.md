# Healthcare Analytics Platform - Agentic RAG System

## Project Context

You're building a **Healthcare Analytics Platform**, an AI-powered system that helps hospital administrators answer questions by combining patient database metrics with policy documents and clinical guidelines. The system intelligently chooses between SQL queries and document searches while handling multi-step analytical queries.

This practice focuses on **Agentic RAG integration** — creating SQL and vector query tools, building an autonomous agent that can reason about which tools to use, and implementing a production-ready REST API that combines structured database queries with semantic document search.

## Problem Statement

Build a production-ready healthcare analytics API that can answer questions using both operational database queries and policy document searches via an intelligent agent. The key challenges are:

1. **Database Connection**: Setting up SQLAlchemy engine and LlamaIndex SQLDatabase wrapper for hospital operations data
2. **Vector Store Integration**: Loading and querying policy documents stored in PostgreSQL with pgvector
3. **Tool Creation**: Creating QueryEngineTool instances for both SQL and vector search capabilities
4. **Agent Orchestration**: Creating an OpenAI agent that can reason about which tools to use for different query types
5. **Query Execution**: Implementing hybrid query execution with tool tracking and response formatting
6. **Error Handling**: Gracefully handling database connection failures, missing indexes, and query errors

You will complete the following implementation tasks to build the healthcare analytics system:

---

### **Task 1 — Initialize Database Engine**

#### Goal

Set up the database connection so the system can communicate with the PostgreSQL database containing hospital operations data.

#### Requirements

1. Read the database connection settings from environment variables (like username, password, host, etc.)
2. Build the complete database connection string that includes all connection details
3. Create a database engine object that can be used to connect to the database

**File**: `main/service/sql_database.py` → `get_db_engine()`

#### Implementation

The implementation uses environment variables with sensible defaults to establish PostgreSQL connectivity. The function retrieves database credentials (user, password, host, port, database name) from the environment, using fallback values like "postgres"/"password" for credentials and "localhost"/"5432" for connection details. The password is URL-encoded using `quote_plus()` to handle special characters safely. A PostgreSQL connection string is constructed in the standard format, and SQLAlchemy's `create_engine()` is used to instantiate the engine, which serves as the connection pool for all database operations throughout the application.

---

### **Task 2 — Create SQL Database Wrapper**

#### Goal

Prepare the database wrapper that allows the agent to query hospital data using natural language questions instead of SQL.

#### Requirements

1. Make sure you have a database engine (create one if it wasn't provided)
2. Specify which database tables should be accessible (use the default hospital tables if none specified)
3. Create a database wrapper that combines the engine and table information

**File**: `main/service/sql_database.py` → `get_sql_database()`

#### Implementation

The function implements a flexible pattern where the database engine can be either provided as a parameter or created on-demand via `get_db_engine()`. If no tables are specified, it defaults to the core hospital operations tables: "patients" and "department_capacity", which expose patient admission data and department resource utilization respectively. LlamaIndex's `SQLDatabase` wrapper is then instantiated with the engine and table list, enabling the natural language query engine to understand which tables are accessible and structure its database schema for LLM reasoning.

---

### **Task 3 — Create Vector Document Tool**

#### Goal

Set up a tool that allows the agent to search through policy documents using semantic search (finding documents by meaning, not just keywords).

#### Requirements

1. Set up the embedding model needed for semantic search (only if it hasn't been set up already)
2. Load the previously stored document index from the database
3. Make sure the index exists (show an error if documents haven't been uploaded yet)
4. Create a search engine from the loaded index
5. Wrap the search engine as a tool that the agent can use, with a clear name and description

**File**: `main/service/tools.py` → `get_vector_tool()`

#### Implementation

The function implements a lazy initialization pattern for Azure OpenAI embeddings, checking if Settings already has an embedding model before creating a new one to avoid redundant initialization. The vector index is loaded from PostgreSQL using `DocumentIngestionPipeline.load_from_db()`, which retrieves previously stored document embeddings from the pgvector table. A validation check ensures documents have been ingested, raising a descriptive error if the table is empty and guiding users to the upload endpoint. The loaded index is converted to a query engine via `as_query_engine()`, and finally wrapped in a `QueryEngineTool` named "policy_documents" with a detailed description indicating it contains healthcare policy documents, quality metrics, safety protocols, compliance information, and guidance on when to use this tool.

---

### **Task 4 — Create SQL Database Tool**

#### Goal

Set up a tool that allows the agent to query hospital database information using natural language questions.

#### Requirements

1. Get the database wrapper that was created in Task

#### Implementation

The function retrieves the SQL database wrapper using `get_sql_database()`, then instantiates an `NLSQLTableQueryEngine` configured with the database connection and accessible table list (patients, department_capacity). The query engine is set to verbose mode to provide detailed execution traces during query processing. The engine is then wrapped in a `QueryEngineTool` named "hospital_database" with a comprehensive description that outlines available data (admission/discharge data, readmission rates, capacity metrics, utilization rates) and usage guidance for operational metrics queries. This tool enables the agent to translate natural language questions like "What is our current ICU capacity?" into SQL SELECT queries and return results. 2
2. Create a query engine that can translate natural language questions into database queries
3. Wrap the query engine as a tool that the agent can use, with a clear name and description explaining what data it contains

**File**: `main/service/tools.py` → `get_sql_tool()`

---

### **Task 5 — Create OpenAI Agent**

#### Goal

Create the intelligent agent that can understand questions and decide which tools to use to answer them.

#### Requirements

1. Check if an agent has already been created (to avoid creating multiple agents)
2. Set up the language model that will power the agent's reasoning
3. Set up the embedding model needed for document search
4. Get both tools (database tool and document search tool) that you created in previous tasks
5. Combine both tools into a list

#### Implementation

The implementation uses a singleton pattern with a global `_agent` variable to ensure only one agent instance exists across the application. On first call, it initializes both Azure OpenAI LLM and embedding models from environment variables, setting them globally via `Settings` so they're reused by other components. The SQL and vector tools created in previous tasks are retrieved and combined into a tools list. The agent is instantiated using `OpenAIAgent.from_tools()` (or `ReActAgent` as a fallback) with a comprehensive system prompt that establishes the agent's role as a healthcare analytics assistant, provides explicit tool usage guidelines (when to use database vs. policy documents vs. both), and includes critical instructions about citing sources, protecting patient privacy, handling comparative analysis, and delivering actionable insights. The agent instance is cached in the global variable and returned, ensuring subsequent calls reuse the same initialized agent.
6. Create the agent with the tools and give it instructions on how to behave as a healthcare analytics assistant
7. Save the agent so it can be reused and return it

**File**: `main/service/agent.py` → `get_agent()`

---

### **Task 6 — Execute Hybrid Query**

#### Goal

Process a user's question by having the agent figure out which tools to use, get the answer, and return it in a structured format.

#### Requirements

1. Get the agent that was created in Task 5
2. Send the user's question to the agent and let it process the ques

#### Implementation

The function is async and retrieves the singleton agent instance via `get_agent()`. It then sends the user's question to the agent using the appropriate method (`chat()` for OpenAIAgent or `run()` for ReActAgent), handling both synchronous and asynchronous execution patterns. The response object is processed to extract the answer, handling multiple response structure patterns (checking for `.response`, `.message`, or stringifying the object directly). Tool usage is extracted using the `_extract_tools_used()` helper function, which analyzes how the agent reached its conclusion. Finally, a `QueryResult` object is constructed containing the original question, generated answer, and list of tools used, which is then formatted for API response consumption with user-friendly source descriptions.tion
3. Figure out which tools the agent used to answer the question
4. Package everything (the question, answer, and tools used) into a result object and return it

**File**: `main/service/query_service.py` → `execute_hybrid_query()`

---

### **Task 7 — Extract Tools Used**

#### Goal

Figure out which tools the agent actually used when answering a question, so users know where the information came from.

#### Requirements

#### Implementation

The function implements multiple extraction strategies to handle different agent response formats. The primary approach checks if the response object has a `sources` attribute containing tool metadata, extracting `tool_name` from each source while avoiding duplicates. When direct source metadata is unavailable, the function falls back to analyzing the question content, using semantic keywords to infer which tools were likely used (e.g., "patient" and "capacity" suggest database usage, while "policy" and "guideline" suggest document search). The `_map_tool_name()` helper function converts internal tool identifiers ("hospital_database", "policy_documents") into user-friendly display names that include both the descriptive name and the internal reference. This approach gracefully handles various agent implementations and response structures while providing transparency about data sources to end users.

1. Create an empty list to collect the tool names
2. Look at the agent's response to see if it mentions which tools were used
3. If that doesn't work, check the agent's conversation history to find which tools it called
4. Convert any technical tool names into user-friendly names that make sense
5. Return the complete list of tools that were used (without duplicates)

**File**: `main/service/query_service.py` → `_extract_tools_used()`

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Database Engine Creation**: The get_db_engine function successfully retrieves all connection parameters from environment variables with proper defaults, constructs the PostgreSQL connection URL correctly, and returns a valid SQLAlchemy engine instance.

2. **SQL Database Wrapper**: The get_sql_database function correctly handles optional engine and include_tables parameters, creates engine if needed, sets default tables, and returns a SQLDatabase instance configured with the correct tables.

3. **Vector Tool Creation**: The get_vector_tool function successfully initializes Azure embeddings if needed, loads vector index from database, validates index existence, creates query engine, and returns QueryEngineTool with proper name and description.

4. **SQL Tool Creation**: The get_sql_tool function successfully retrieves SQL database, creates NLSQLTableQueryEngine with correct tables and verbose mode, and returns QueryEngineTool with proper name and description.

5. **Agent Creation**: The get_agent function correctly implements singleton pattern, initializes LLM and embedding models with proper environment variables, retrieves both tools, creates OpenAIAgent with tools and healthcare-specific system prompt, and returns the configured agent.

6. **Query Execution**: The execute_hybrid_query function correctly retrieves agent, executes query, extracts tools used, and returns QueryResult with all required fields.

7. **End-to-End Flow**: The complete system processes healthcare queries through API route endpoint → query service → agent execution → tool selection → database/document queries → response formatting → API response, successfully returning structured answers with tool usage information for all three query categories (database-only, document-only, and hybrid queries).
