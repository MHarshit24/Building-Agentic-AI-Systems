# LLM App with GitHub Copilot

FastAPI application demonstrating **LLM integration with Gemini**, **rate limiting**, and **streaming responses** enhanced with **[GitHub Copilot prompts](COPILOT_PROMPTS.md)** for AI-powered code improvement and best practices.

---

## Features

* **FastAPI REST API**: Production-ready endpoints with automatic documentation
* **LLM Integration**: Google Gemini via OpenAI-compatible SDK
* **Rate Limiting**: Built-in protection (2 requests per minute)
* **Streaming Responses**: Real-time text generation with SSE
* **Error Handling**: Robust error management and validation
* **Comprehensive Testing**: Integration tests with pytest
* **GitHub Copilot Prompts**: Ready-to-use prompts for code enhancement

---

## Project Structure

```bash
demo-1-llm-app-with-copilot/
├── main.py                      # FastAPI application
├── .env                         # Environment variables
├── pyproject.toml              # Project dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project documentation
├── COPILOT_PROMPTS.md         # GitHub Copilot prompts
├── tests/
│   ├── __init__.py
│   └── test_integration.py    # Integration tests
└── uv.lock                     # Locked dependencies
```

---

## Setup

### 1. Install Dependencies

```bash
uv sync
```

---

### 2. Configure Environment Variables

Change the filename from `.envbackup` to `.env`, and include the appropriate keys within it.

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL_NAME=gemini-2.5-flash
```
**Note**: The GEMINI_MODEL value can be updated to any supported model. Model names may change over time, so always refer to the latest options in Google’s documentation.

---

### 3. Run the Application

Start the development server using `uv`:

```bash
uv run uvicorn main:app --reload
```

The API will be available at: `http://localhost:8000`

---

### 4. Access API Documentation

Open your browser and navigate to:

* **Swagger UI**: `http://localhost:8000/docs`
* **ReDoc**: `http://localhost:8000/redoc`

---

## Usage

### POST /ask

Ask a question and receive a complete response.

**Request**:
```json
{
  "prompt": "What is Python?"
}
```

**Response**:
```json
{
  "answer": "Python is a high-level programming language..."
}
```

**Rate Limit**: 2 requests per minute

---

### POST /ask/stream

Ask a question and receive a streaming response.

**Request**:
```json
{
  "prompt": "Explain machine learning"
}
```

**Response**: Server-Sent Events (SSE) text stream

**Rate Limit**: 2 requests per minute

---

## Example Output

### Standard Response (`/ask`)

```bash
POST http://localhost:8000/ask
{
  "prompt": "What are list comprehensions in Python?"
}

Response:
{
  "answer": "A list comprehension is a compact way to create lists in Python.
  Example: [x**2 for x in range(5)] → [0, 1, 4, 9, 16]"
}
```

### Streaming Response (`/ask/stream`)

```bash
POST http://localhost:8000/ask/stream
{
  "prompt": "Explain machine learning in simple terms"
}

Response (streaming):
Machine learning is a subset of artificial intelligence...
(text streams in real-time)
```

---

## Testing

### Run Tests

```bash
uv run pytest -v
```

### Run Tests with Coverage

```bash
uv run pytest --cov=main --cov-report=term
```

### Generate HTML Coverage Report

```bash
uv run pytest --cov=main --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

---

## Key Concepts

| Step | Concept                  | Description                                      |
| ---- | ------------------------ | ------------------------------------------------ |
| 1    | Environment Management   | Load secrets securely using `python-dotenv`      |
| 2    | FastAPI Setup            | Create REST endpoints with automatic validation  |
| 3    | LLM Integration          | Configure OpenAI SDK with Gemini `base_url`      |
| 4    | Rate Limiting            | Protect API with Slowapi middleware              |
| 5    | Streaming Responses      | Implement SSE for real-time text generation      |
| 6    | Error Handling           | Manage authentication and network issues         |
| 7    | Testing                  | Integration tests with mocking and assertions    |
| 8    | GitHub Copilot           | Use AI-powered prompts for code enhancement      |

---

## GitHub Copilot Setup

### 1. Install Extensions

1. Open VS Code Extensions (`Ctrl+Shift+X` or `Cmd+Shift+X`)
2. Search and install:
   - **GitHub Copilot**
   - **GitHub Copilot Chat**
3. Sign in with your GitHub account
4. Verify Copilot icon is active in status bar

### 2. Use Copilot Prompts

See **[COPILOT_PROMPTS.md](COPILOT_PROMPTS.md)** for comprehensive prompts.



---

## Troubleshooting

**Issue**: Tests are slow  
**Solution**: Rate limits apply (2/min). Tests wait between requests.

**Issue**: API key error  
**Solution**: Verify `GEMINI_API_KEY` is set correctly in `.env`

**Issue**: Import errors  
**Solution**: Run `uv sync` to install all dependencies

**Issue**: Port already in use  
**Solution**: Stop other services on port 8000 or use `--port 8001` flag

---

## Learning Resources

* [COPILOT_PROMPTS.md](COPILOT_PROMPTS.md) - All Copilot prompts for code improvement
* [FastAPI Documentation](https://fastapi.tiangolo.com/)
* [GitHub Copilot Docs](https://docs.github.com/en/copilot)
* [Gemini API Documentation](https://ai.google.dev/docs)

---

## Summary

A production-ready **FastAPI application** demonstrating **LLM integration with Google Gemini**, featuring **rate limiting**, **streaming responses**, and comprehensive **GitHub Copilot prompts** for AI-powered code enhancement. Built with `uv` for modern Python dependency management and includes full test coverage.

**Ready to enhance your code with AI?** Check out [COPILOT_PROMPTS.md](COPILOT_PROMPTS.md)!
