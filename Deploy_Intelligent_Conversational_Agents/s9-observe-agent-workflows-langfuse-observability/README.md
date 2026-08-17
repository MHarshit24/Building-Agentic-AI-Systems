## Project Context

In earlier practice, you built a full-stack LLM application with FastAPI and LangChain.  
However, without observability, it's difficult to understand how your application behaves in production — you can't see traces, token usage, costs, or correlate requests by session and user.

In this practice, you will add end-to-end observability to your LLM application using two approaches:
- Using a lightweight `@observe` decorator (Langfuse) combined with **OpenTelemetry** spans
- Using the **Langfuse Callback Handler** to automatically trace LangChain executions, tokens, and costs with session/user correlation

By the end, your app will be fully observable: you'll see traces, spans, token usage, and be able to correlate requests by session and user.

---

## Problem Statement

Implement observability in your existing FastAPI + LangChain application using two complementary approaches: the `@observe` decorator with OpenTelemetry spans for security operations, and the Langfuse Callback Handler for comprehensive chain tracing with session/user metadata.  
You will complete **two main tasks**:

---

### **Task 1 — Add Observability with `@observe` Decorator**

#### Goal  
Apply the `@observe` decorator to security functions to observe authentication and authorization behavior, and optionally initialize OpenTelemetry so spans are visible in logs.

#### Requirements  
1. Add the `@observe` decorator to functions such as token validation and user info lookup (e.g., authentication and authorization logic).

2. Initialize OpenTelemetry with a Console exporter so spans are visible in logs.

3. Add a shutdown hook to flush traces if you enabled a tracer/exporter.

4. Configure Langfuse environment variables to send traces to Langfuse (if using cloud or self-hosted instance).

#### Implementation Notes

**`observability.py`**
- A `TracerProvider` is created and configured with a `BatchSpanProcessor` wrapping a `ConsoleSpanExporter`, which prints completed spans as structured JSON to the terminal during every request.
- The provider is registered globally via `trace.set_tracer_provider(provider)`, meaning all modules in the process share the same tracing backend automatically.
- A named module-level `tracer` is obtained via `trace.get_tracer(__name__)` for use in creating custom spans if needed.
- The Langfuse client singleton is obtained via `get_client()` and exposed through a `flush_langfuse()` helper that is called during application shutdown to drain any buffered traces.

**`security.py`**
- The `@observe()` decorator is applied to three functions: `_fetch_jwks`, `get_user_email_from_auth0`, and `validate_token`.
- Because `validate_token` calls `_fetch_jwks` internally, Langfuse automatically nests `_fetch_jwks` as a **child span** inside the `validate_token` span, giving a complete call tree of the authentication flow.
- The `observe` decorator is imported from the shared `observability` module so all decorated functions feed into the same tracer and Langfuse client.

**Environment Variables Required (Task 1)**
- `LANGFUSE_PUBLIC_KEY` — identifies your Langfuse project
- `LANGFUSE_SECRET_KEY` — authenticates the SDK with your Langfuse account
- `LANGFUSE_HOST` — target Langfuse server (e.g. `https://cloud.langfuse.com` for the hosted version)

These are loaded automatically by the Langfuse SDK from the `.env` file via `load_dotenv()`. They never need to be passed explicitly in code.

---

### **Task 2 — Add Observability with Langfuse Callback Handler**

#### Goal  
Attach the Langfuse Callback Handler in your chat API so all chain events (LLM calls, tokens, costs) and metadata (session/user) are captured automatically.

#### Requirements  
1. Implement a callback manager that can return a configured Langfuse callback handler.

2. Create a helper function that:
   - Resolves the user identity from the JWT payload (e.g., email, user ID).
   - Creates a callback handler instance and builds a chain configuration with:
     - Callbacks including the handler
     - Metadata including `session_id`, `user_id`/`user_email`, `trace_name`, and relevant tags.

3. Update your chat endpoint to execute the chain with the configured callbacks and stream responses.

4. Ensure traces are flushed (e.g., in a `finally` block) to avoid losing the tail of a streamed response.

5. Configure Langfuse environment variables for the callback handler.

#### Implementation Notes

**`langfuse_callback.py`**
- A `Langfuse()` client instance is created at module load time. It automatically reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` from the environment — no manual key passing is needed.
- `get_langfuse_manager()` is the single factory function for all callback setup. It creates a bare `CallbackHandler()` instance (no constructor arguments, as this SDK version reads metadata from the LangChain config dict at runtime instead).
- The returned `config` dict contains two keys: `"callbacks"` which plugs the handler into the LangChain event system, and `"metadata"` which carries `session_id`, `user_id`, and `trace_name` that Langfuse stamps onto every trace for filtering in the dashboard.
- Both the `config` dict and the raw `handler` are returned — `config` goes into the chain call, `handler` is kept so it can be flushed after streaming ends.

**`main.py`**
- `setup_langfuse_callback()` bridges JWT auth data and Langfuse config: it extracts the user's email from the decoded token payload and calls `get_langfuse_manager()`, keeping the chat endpoint clean.
- After `get_langfuse_manager()` returns, a `"configurable"` key with `session_id` is merged into the same config dict. This is what `RunnableWithMessageHistory` reads to look up the correct in-memory chat history — it must live in `config["configurable"]`, not in `metadata`.
- `flush_langfuse_traces()` calls `callback_handler.flush()` after checking the handler is not `None`. This is placed in the `finally` block of the streaming generator so it runs whether the stream completes, errors, or is cancelled by the client disconnecting.
- The `@app.on_event("shutdown")` hook calls `flush_langfuse()` from `observability.py` as a second safety net, draining any traces buffered across all requests before the process exits.

**Environment Variables Required (Task 2)**
- Same `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` as Task 1 — the callback handler reads them from the same `.env` file automatically.

---

## Evaluation Criteria

Ensure you evaluate your solution against the below criteria:

1. **Decorator Usage**: Ensure the @observe decorator is correctly applied so observability hooks trigger during chain execution.
   - ✅ Applied to `validate_token`, `_fetch_jwks`, and `get_user_email_from_auth0` in `security.py`. The console logs confirm nested spans are being generated — `_fetch_jwks` appears as a child of `validate_token` with a matching `parent_id`.

2. **Span Logging**: Make sure OpenTelemetry spans are properly initialized and visible in the console logs during request processing.
   - ✅ `ConsoleSpanExporter` is configured in `observability.py` via `BatchSpanProcessor`. Spans print as structured JSON to the terminal on every authenticated request, as visible in the server output above.

3. **Callback Setup**: Ensure the Langfuse Callback Handler is correctly configured and attached to all chain executions.
   - ✅ `CallbackHandler()` is instantiated in `get_langfuse_manager()` and returned inside a `config` dict that is passed directly to `stateful_chain.astream()` on every `/chat` request.

4. **Trace Metadata**: Make sure traces include important metadata such as session_id, user_email, and trace_name for clear correlation across requests.
   - ✅ `session_id`, `user_id` (email from JWT), and `trace_name` are included in `config["metadata"]` and stamped onto every Langfuse trace. The user email is extracted from the decoded JWT payload in `setup_langfuse_callback()`.

5. **Trace Flushing**: Ensure traces are properly flushed so no telemetry data is lost during or after streamed responses.
   - ✅ `callback_handler.flush()` is called in the `finally` block of the streaming generator in `main.py`. A second flush via `flush_langfuse()` runs on application shutdown via the `@app.on_event("shutdown")` hook.