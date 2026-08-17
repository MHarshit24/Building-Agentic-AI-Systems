## Project Context

You've already built the core travel suggestion engine in earlier practice — it can generate itineraries and structured outputs.  
Now, it's time to make your **Trip & Travel Agent** smarter by giving it **tools** it can use to fetch information, reason about data, and respond intelligently.


---

## Problem Statement

Equip your **Travel & Trip Planner Agent** with tools and intelligence by creating tools with internal logic and external API integration, then combining them into an intelligent agent that can automatically select and use the appropriate tools based on user queries.  
You will complete **three main tasks**:

---

### **Task 1 — Create and Test an Internal Tool (`get_destination_info`)**

#### Goal
Create an internal tool that uses the Gemini LLM to fetch and summarize travel-related details for any destination.

#### Requirements
1. Implement a tool function in `travel_tools.py` that uses an LLM to generate travel summaries for destinations, including information about visiting months, attractions, and notable features.

2. Make sure the function can be registered as a tool, returns structured data, and includes proper error handling.

3. Create a FastAPI POST endpoint `/tools/internal` that accepts destination input, invokes the tool, and returns the travel information as a JSON response.

#### Implementation Details

**Tool Function (`travel_tools.py`):**
- The `get_destination_info` function is decorated with LangChain's `@tool` decorator to register it as a callable tool
- Takes a destination string as input and validates that it's not empty
- Constructs a detailed prompt instructing the LLM to generate location-specific travel information
- Uses ChatOpenAI (configured with Gemini/GPT-3.5-turbo) to generate structured travel data
- Returns JSON containing `best_time_to_visit`, `top_attractions` (as an array), and `notable_features`
- Implements robust error handling for input validation, LLM response parsing, and JSON formatting
- Falls back to a generic JSON structure if the LLM response cannot be parsed as valid JSON

**FastAPI Endpoint (`main.py`):**
- The `/tools/internal` POST endpoint accepts a destination parameter
- Invokes the `get_destination_info` tool using LangChain's `invoke()` method
- Parses the returned JSON string back to a Python dictionary for the response
- Catches any exceptions during tool execution and returns HTTP 500 errors with error details

**Key Features:**
- Input validation prevents processing of empty or invalid destination names
- LLM prompt is specifically designed to ensure location-accurate information
- Structured JSON output ensures consistent data format for frontend consumption
- Comprehensive error handling prevents API crashes from malformed inputs or LLM failures

---

### **Task 2 — Create and Test an External API Tool (`get_user_location`)**

#### Goal
Create a LangChain tool that fetches the user's current location using an external geolocation API to provide localized recommendations.

#### Requirements
1. Configure environment variables with the required API key for the external geolocation service.

2. Implement a tool function in `travel_tools.py` that connects to an external geolocation API and retrieves user location data (e.g., IP, city, region, country).

3. Ensure the function can be registered as a tool and includes proper error handling for API failures, network issues, and missing credentials.

4. Create a FastAPI endpoint `/tools/external` that invokes the tool and returns location data as a JSON response.

#### Implementation Details

**Tool Function (`travel_tools.py`):**
- The `get_user_location` function uses LangChain's `@tool` decorator for tool registration
- Validates that the `APIIP_API_KEY` environment variable is set before making API calls
- Makes HTTP GET requests to the apiip.net geolocation service with a 5-second timeout
- Extracts and returns user location data including IP address, city, region/state, and country
- Implements comprehensive error handling for multiple failure scenarios:
  - API key validation failures
  - Network timeouts (using requests.exceptions.Timeout)
  - HTTP error status codes (non-200 responses)
  - General network exceptions (using requests.exceptions.RequestException)
  - JSON parsing errors and other unexpected exceptions
- Returns structured error messages in JSON format instead of crashing

**FastAPI Endpoint (`main.py`):**
- The `/tools/external` POST endpoint requires no input parameters (uses empty string for tool invocation)
- Calls the `get_user_location` tool and parses the JSON response
- Converts any exceptions during tool execution into HTTP 500 status codes with descriptive error messages

**Key Features:**
- Environment variable validation ensures API credentials are properly configured
- Multiple layers of error handling prevent API failures from crashing the application
- Timeout protection prevents hanging requests that could block the server
- Structured error responses provide clear feedback about what went wrong
- Location data extraction focuses on the most relevant fields for travel recommendations

**Environment Variables Required:**
- `APIIP_API_KEY`: Authentication key for the apiip.net geolocation service

---

### **Task 3 — Build an Intelligent Travel Agent**

#### Goal
Combine both tools into a single agent that automatically decides which tool(s) to use based on the user query.

#### Requirements
1. Set up an agent using `create_agent` that combines both tools and is configured with a custom system prompt to guide tool selection based on user queries.

2. Configure the agent to automatically select the appropriate tool(s) for different query types (e.g., location-based queries, destination-specific queries).

3. Create a FastAPI POST endpoint `/ask` that accepts user queries, invokes the agent, and returns the agent's response.

#### Implementation Details

**Agent Setup (`main.py`):**
- Imports both `get_destination_info` and `get_user_location` tools from the travel_tools module
- Initializes a ChatOpenAI model with temperature 0.3 for consistent, focused responses
- Creates a tools list containing both imported tool functions
- Defines a custom system prompt that explicitly instructs the agent on when to use each tool:
  - For location-based queries ("places near me", "visit my area"), first call `get_user_location`, then `get_destination_info`
  - Emphasizes automatic tool calling without asking follow-up questions
- Uses LangChain's `create_agent` function to build a ReAct (Reasoning + Acting) agent with the model, tools, and system prompt

**Agent Endpoint (`main.py`):**
- The `/ask` POST endpoint accepts a user query string parameter
- Invokes the agent using the `invoke()` method with a properly formatted messages structure
- Extracts the final AI response from the agent's output by iterating through the response messages in reverse order
- Returns a clean JSON response containing only the agent's final answer
- Implements exception handling to catch agent execution errors and return HTTP 500 responses

**Key Features:**
- ReAct agent architecture enables reasoning about which tools to use before taking actions
- Custom system prompt provides clear decision-making rules for tool selection
- Automatic tool chaining (location detection followed by destination information)
- Response extraction logic handles LangChain's message-based output format
- Error handling prevents agent failures from crashing the API
- Clean JSON responses suitable for frontend integration

**Example Query Processing:**
- Query: "What places should I visit near me?" → Agent calls `get_user_location` first, then uses the city name with `get_destination_info`
- Query: "Tell me about Paris" → Agent directly calls `get_destination_info` with "Paris"
- Query: "Where am I?" → Agent calls `get_user_location` and returns location data

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Tool Configuration**: Ensure both tools (get_destination_info and get_user_location) are imported, registered, and ready for the agent to invoke.
2. **Agent Logic**: Make sure the ReAct agent is created with the correct system prompt so it can automatically call tools without follow-up questions.
3. **Route Handling**: Ensure each FastAPI route correctly invokes the corresponding tool or agent and returns clean JSON responses.
4. **Error Management**: Make sure appropriate exceptions are caught and converted into HTTP errors to prevent the API from crashing.


---

## Environment Setup

Create a `.env` file in the project root directory with the following variables:

```env
OPENROUTER_API_KEY=your_openai_api_key
OPENROUTER_BASE_URL=https://api.openai.com/v1
OPENROUTER_MODEL=openai/gpt-3.5-turbo
APIIP_API_KEY=your_apiip_api_key
```

**Required Variables:**
- `OPENROUTER_API_KEY`: OpenAI API key used by ChatOpenAI for LLM-powered destination information generation
- `OPENROUTER_BASE_URL`: Base URL for the LLM API service (defaults to OpenAI's API)
- `OPENROUTER_MODEL`: Specific model name to use for LLM calls (defaults to GPT-3.5-turbo)
- `APIIP_API_KEY`: API key for the apiip.net geolocation service used by the location tool

---

## Running the Application

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```

   The server will run on: `http://localhost:8000`

3. **API Documentation:**
   - Interactive Swagger UI: `http://localhost:8000/docs`
   - Alternative ReDoc format: `http://localhost:8000/redoc`

---

## Testing the Endpoints

### Test Internal Tool: POST `/tools/internal`
Fetches travel information about a specific destination using LLM-generated content.

**Request:**
```bash
curl -X POST "http://localhost:8000/tools/internal?destination=Paris"
```

**Expected Response:**
```json
{
  "best_time_to_visit": "April to June and September to October",
  "top_attractions": [
    "Eiffel Tower",
    "Louvre Museum",
    "Notre-Dame Cathedral"
  ],
  "notable_features": "City of Light with stunning architecture and world-class museums"
}
```

### Test External Tool: POST `/tools/external`
Retrieves the user's current location based on their IP address.

**Request:**
```bash
curl -X POST "http://localhost:8000/tools/external"
```

**Expected Response:**
```json
{
  "ip": "203.0.113.45",
  "city": "New York",
  "region": "New York",
  "country": "United States"
}
```

### Test Agent: POST `/ask`
Sends a natural language query to the intelligent agent, which automatically determines which tools to use.

**Request:**
```bash
curl -X POST "http://localhost:8000/ask?query=What places should I visit near me"
```

**Expected Response:**
```json
{
  "response": "Based on your location in New York, I recommend visiting these attractions: Central Park, Statue of Liberty, Times Square, and the Metropolitan Museum of Art. The best time to visit is during spring (April-May) or fall (September-October) when the weather is mild."
}
```

**Additional Example Queries:**
- "Tell me about Tokyo" → Direct destination information lookup
- "Where am I located?" → Location detection only
- "Suggest places to visit in my city" → Combined location detection and destination information

---

## Project Files

- **`main.py`**: Contains the FastAPI application with three endpoints, agent initialization, and LLM model setup
- **`travel_tools.py`**: Implements both LangChain tools with comprehensive error handling and external API integration
- **`pyproject.toml`**: Defines project metadata and Python package dependencies
- **`README.md`**: This comprehensive documentation file

---

## Key Libraries Used

- **FastAPI**: Modern web framework for building REST APIs with automatic OpenAPI documentation
- **LangChain**: Framework for building applications with large language models and tool integration
- **LangChain-OpenAI**: OpenAI integration providing ChatOpenAI for LLM interactions
- **Uvicorn**: ASGI server implementation for running FastAPI applications
- **Requests**: HTTP library for making external API calls to geolocation services
- **Python-dotenv**: Environment variable management for secure API key storage
