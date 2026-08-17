## Study Buddy: Personalized AI Tutoring API with PostgreSQL

A modern FastAPI application that integrates with Gemini to explain concepts and automatically stores conversations in PostgreSQL. This practice gives you a step-by-step path to use Github Coplit to implement the API, database schema, services, and tests.

### Problem Statement

In this practice you will use GitHub Copilot all modes(Ask, Edit and Agent) to enhance, test, and refactor existing Python code.
Your goal is to understand how Copilot can assist across different coding tasks — from explaining and documenting code to generating tests, storing data, and refactoring projects.

#### Context

In this Practice, you’ll explore how GitHub Copilot can act as your coding partner.
You’ll try different prompt types — Ask Mode and Agent Mode — to see how Copilot can explain, review, document, test, store data, and refactor code.
This will help you understand how to use Copilot effectively across real-world coding tasks.

### What You Will Build

You’ll work on a Python project where Copilot helps you:
- Explain and review existing code
- Add documentation for better readability
- Generate and run tests for ~70% coverage
- Store user queries in a PostgreSQL database using SQLAlchemy
- Refactor the app into separate route and service files

By the end, you’ll have a modular, testable, and database-enabled app — built with help from Copilot!


#### Task Details

Following steps should be performed to build the solution for this practice.

1. Explain Code (Ask Mode) – Ask Copilot to explain the code in simple terms.

2. Review Code (Ask Mode) – Get Copilot’s feedback on what can be improved.

3. Add Documentation (Edit Mode) – Use Copilot to add comments and docstrings.

4. Generate Tests –
  - Ask Copilot to plan unit tests for ~70% coverage.
  - Create test cases in the /test folder using Agent Mode.

5. Store Data (Agent Mode) –
  - Use SQLAlchemy to insert user query details into PostgreSQL.
  - Create query_model.py and db_operations.py.
  - Update main.py to call the insert function.

6. Refactor Code (Agent Mode) –
   - Keep main.py unchanged.
   - Create modular_main.py for routes and llm_app_service.py for services.


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
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL=gemini-2.0-flash
```

**Get API Keys:**
- **Gemini**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey)

### 5. Run Application

```bash
uv run uvicorn main:app --reload
```


```bash
uv run uvicorn maindemo:app --reload
```
Visit: http://localhost:8000/docs


Run tests:

```bash
uv run pytest
```

### Run the App

```bash
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs