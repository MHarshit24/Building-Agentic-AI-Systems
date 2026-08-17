# 💡 Code Mentor – AI Pair Programmer

An intelligent AI-powered coding companion that helps developers understand code, debug issues, improve implementations, and learn best practices through real-time assistance.

---

## 📌 Problem Statement

Developers often face challenges such as:

* ⏱️ Time-consuming debugging
* 🤯 Difficulty understanding unfamiliar code
* 📚 Over-reliance on scattered documentation
* 🧠 Applying best practices consistently
* 🔄 Breaking focus while searching for solutions

Traditional tools lack **real-time, contextual guidance**, making development inefficient.

---

## 🎯 Project Goal

To build an **AI-powered Pair Programmer** that provides:

* Real-time code explanations
* Bug detection and debugging assistance
* Code optimization and improvements
* Best practice recommendations
* Personalized suggestions based on user experience

---

## 🚀 Features

### 🔍 Code Analysis

* Detects bugs, inefficiencies, and bad practices
* Provides structured feedback

### 📖 Code Explanation

* Simplifies complex logic
* Tailored explanations based on:

  * Beginner
  * Intermediate
  * Expert

### ⚡ Code Improvement

* Suggests optimized implementations
* Provides performance insights

### 🧠 Code Review

* Scores code quality
* Detects:

  * Issues
  * Security risks
  * Maintainability concerns

### 🌊 Streaming AI Response

* Real-time output using streaming API

### 🧾 Feedback System

* Stores user feedback in:

  * PostgreSQL database
  * JSON logs

### 🔒 Rate Limiting

* Prevents API abuse using `slowapi`

---

## 🏗️ Tech Stack

| Technology            | Purpose                |
| --------------------- | ---------------------- |
| **FastAPI**           | Backend API framework  |
| **Uvicorn**           | ASGI server            |
| **Google Gemini API** | AI code analysis       |
| **Pydantic**          | Data validation        |
| **PostgreSQL**        | Data storage           |
| **SlowAPI**           | Rate limiting          |
| **Pytest**            | Unit testing           |
| **dotenv**            | Environment management |

---

## 📂 Project Structure

```
app/
│── config/            # Environment settings
│── models/            # Request & response schemas
│── routes/            # API endpoints
│── services/          # Business logic & AI calls
│── utils/             # Helpers (DB, logger, prompt builder)
│── main.py            # FastAPI entry point

tests/                 # Unit & integration tests

.env                   # Environment variables
requirements.txt       # Dependencies
pyproject.toml         # Project config
```

---

## ⚙️ Environment Variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-flash
POSTGRES_DB=code_mentor_db
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

![Code Mentor](ChatGPT%20Image%20Mar%2017%2C%202026%2C%2009_22_50%20PM.png)

---

## 🛠️ Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone <your-repo-url>
cd code-mentor
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # macOS/Linux
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Setup PostgreSQL

Create the database in PostgreSQL:

```sql
CREATE DATABASE code_mentor_db;
```

Then add your credentials to the `.env` file as shown in the Environment Variables section above.

---

## ▶️ Running the Application

```bash
uvicorn app.main:app --reload
```

Access API at:

```
http://127.0.0.1:8000
```

Swagger Docs:

```
http://127.0.0.1:8000/docs
```

---

## 📡 API Endpoints

| Endpoint               | Method | Description        |
| ---------------------- | ------ | ------------------ |
| `/analyze-code`        | POST   | Analyze code       |
| `/analyze-code/stream` | POST   | Stream analysis    |
| `/explain-code`        | POST   | Explain code       |
| `/improve-code`        | POST   | Improve code       |
| `/review-code`         | POST   | Full code review   |
| `/feedback`            | POST   | Save user feedback |

---

## 📥 Sample Request

```json
{
  "code": "def add(a,b): return a+b",
  "language": "python",
  "experience_level": "beginner"
}
```

---

## 🧪 Running Tests

```bash
pytest --cov=app tests/
```

For a detailed HTML coverage report:

```bash
pytest --cov=app --cov-report=html tests/
```

---

## 🧠 How It Works

1. User submits code
2. Language is detected automatically
3. Prompt is dynamically generated based on task and experience level
4. Gemini API processes the request
5. Response is parsed into structured output
6. Logs are saved in PostgreSQL
7. Results returned to user

---

## 🔐 Error Handling

| Status Code | Meaning                  |
| ----------- | ------------------------ |
| 400         | Bad Request              |
| 422         | Validation Error         |
| 429         | Rate Limit Exceeded      |
| 503         | AI Service Unavailable   |
| 500         | Internal Server Error    |

---

## 📊 Key Highlights

* ✅ Clean modular architecture
* ✅ Strong validation using Pydantic
* ✅ Streaming AI responses
* ✅ Database logging + feedback system
* ✅ Fully tested with Pytest
* ✅ Rate limiting implemented

---

## 🚧 Future Enhancements

* 🔹 Frontend UI (React / Streamlit)
* 🔹 Support for more LLMs (OpenAI, Ollama local models)
* 🔹 Code history tracking
* 🔹 Personalized AI fine-tuning
* 🔹 IDE integration (VS Code Extension)

---

## 👩‍💻 Authors

| Name           |
| -------------- |
| Harshit Mutha  |
| Nupur Sawant   |

---

## ⭐ Acknowledgements

* Google Gemini API
* FastAPI community
* Open-source contributors

---

## 📜 License

This project is for educational and learning purposes.