# AI Query Assistant API

> **Intelligent Question & Answer System with PostgreSQL Storage**

A modern FastAPI application that integrates with AI models (Gemini) to answer questions and automatically stores the conversation history in a PostgreSQL database. Enhanced with **[GitHub Copilot prompts](COPILOT_PROMPTS.md)** for AI-powered code improvement. Perfect for learning FastAPI, database operations, AI integration, and modern web development patterns.

## Features

- **AI Integration**: Ask questions directly to Gemini AI models
- **Auto-Storage**: Automatically saves questions and responses to PostgreSQL
- **API Documentation**: Auto-generated OpenAPI/Swagger docs

## Project Structure

```text
demo-2-console-llm-app-to-rest-api/
├── main.py              # FastAPI application with query endpoint
├── pyproject.toml       # Project dependencies & metadata
├── uv.lock              # Dependency lock file
├── .env                 # Environment variables (create this)
└── README.md            # This file
```

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- UV package manager (recommended) or pip

## PostgreSQL Installation

### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install PostgreSQL 18
sudo apt install postgresql-18 postgresql-client-18

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Set password for postgres user
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your_password';"
```

### Windows

1. **Download**: Visit [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)
2. **Install**: Run the installer and follow the setup wizard
3. **Configure**: Set password for `postgres` user during installation
4. **Verify**: Open Command Prompt and run:
   ```cmd
   psql --version
   ```

### macOS

```bash
# Using Homebrew (recommended)
brew install postgresql@18

# Start PostgreSQL service
brew services start postgresql@18

# Create postgres user with password
createuser -s postgres
psql postgres -c "ALTER USER postgres PASSWORD 'your_password';"
```

**Alternative (macOS):**
- Download from [PostgreSQL.app](https://postgresapp.com/) for GUI installation

### Verify Installation

```bash
# Check PostgreSQL version
psql --version

# Connect to database
psql -U postgres -h localhost
```

### 1. Clone and Navigate

```bash
cd s10-enhance-code-using-ai-tools/demo-2-crud-using-postgres
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Setup Database

Create PostgreSQL database:

```bash
# Create database
createdb llm_queries_db

# Or using psql
PGPASSWORD=your_password psql -U postgres -h localhost -d postgres -c "CREATE DATABASE llm_queries_db;"
```
### Explore Database Details
-- List all databases
\l

-- Connect to a specific database
\c llm_queries_db

-- List all tables in the current database
\dt

-- View columns of a specific table
\d table_name

-- Run a query to see table contents
SELECT * FROM table_name;

### 4. Configure Environment

Create `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/llm_queries_db

# AI Service Configuration
```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL_NAME=gemini-2.5-flash
```
**Note**: The GEMINI_MODEL value can be updated to any supported model. Model names may change over time, so always refer to the latest options in Google’s documentation.

**Get API Keys:**
- **Gemini**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey)

---

### 5. Run Application

```bash
uv run uvicorn main:app --reload
```


```bash
uv run uvicorn maindemo:app --reload
```
Visit: http://localhost:8000/docs

## API Documentation

### Core Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `POST` | `/queries/ask` | Ask AI a question | `{"question": "Your question"}` |

### Example Usage

#### Ask AI a Question

```bash
curl -X POST "http://localhost:8000/queries/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is FastAPI?"}'
```

**Response:**
```json
{
  "answer": "FastAPI is a modern, fast web framework for building APIs with Python 3.7+ based on standard Python type hints...",
}
```

#### List All Queries

```bash
curl "http://localhost:8000/queries/?skip=0&limit=10"
```

#### Delete a Query

```bash
curl -X DELETE "http://localhost:8000/queries/1"
```

## Database Schema

The `queries` table stores conversation history:

```sql
CREATE TABLE queries (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    response TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Key Technologies

- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: Python SQL toolkit and ORM
- **PostgreSQL**: Robust relational database
- **Pydantic**: Data validation using Python type hints
- **Pytest**: Testing framework
- **OpenAI SDK**: For Gemini AI integration

**Ready to enhance your code with AI?** Check out [COPILOT_PROMPTS.md](COPILOT_PROMPTS.md)!
