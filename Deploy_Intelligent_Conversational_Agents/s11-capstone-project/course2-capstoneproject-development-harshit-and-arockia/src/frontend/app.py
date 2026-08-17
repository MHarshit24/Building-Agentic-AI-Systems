"""
Job Placement Agent — Streamlit Frontend
=========================================
Communicates with the backend exclusively via gRPC (protobuf, no JSON).

Transport : gRPC (binary protobuf over TCP)
Server    : GRPC_HOST:GRPC_PORT  (default localhost:50051)

The frontend only uses public RPCs (no Auth0 token required):
  HealthCheck  — connection probe
  ChatPublic   — conversational agent
"""

import os
import sys
import uuid

import grpc
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Locate the backend proto package ─────────────────────────────────────────
# The generated pb2 stubs live in src/backend/proto/.
# Insert the backend directory so `from proto import ...` resolves correctly.
_BACKEND_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "backend")
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from proto import job_agent_pb2, job_agent_pb2_grpc  # noqa: E402

# ── Configuration ─────────────────────────────────────────────────────────────
GRPC_HOST       = os.getenv("GRPC_HOST",    "localhost")
GRPC_PORT       = int(os.getenv("GRPC_PORT", "50051"))
REQUEST_TIMEOUT = 120   # seconds — agent tool calls can be slow

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Placement Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .stApp { background-color: #f0f4f8; }
    section[data-testid="stSidebar"] { background-color: #1e3a5f; color: white; }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p { color: #e8f0fe !important; }
    .chat-user {
        background: #1e3a5f; color: white;
        border-radius: 16px 16px 4px 16px;
        padding: 12px 16px; margin: 6px 0; max-width: 80%;
        margin-left: auto; word-wrap: break-word;
    }
    .chat-assistant {
        background: white; color: #1a1a2e;
        border-radius: 16px 16px 16px 4px;
        padding: 12px 16px; margin: 6px 0; max-width: 85%;
        border: 1px solid #e0e6ed; word-wrap: break-word;
    }
    .stButton > button {
        border-radius: 20px; border: 1.5px solid #1e3a5f;
        color: #1e3a5f; background-color: white;
        font-weight: 500; transition: all 0.2s;
    }
    .stButton > button:hover { background-color: #1e3a5f; color: white; }
    .agent-title   { font-size: 2rem; font-weight: 700; color: #1e3a5f; }
    .agent-subtitle { color: #5a7ea6; font-size: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── gRPC client (cached across all Streamlit sessions) ────────────────────────

@st.cache_resource
def _get_stub() -> job_agent_pb2_grpc.JobAgentServiceStub:
    """
    Create a single shared gRPC channel + stub for the lifetime of the process.

    st.cache_resource is used so the channel is opened once and reused for
    every Streamlit user session — gRPC channels are thread-safe.
    """
    channel = grpc.insecure_channel(f"{GRPC_HOST}:{GRPC_PORT}")
    return job_agent_pb2_grpc.JobAgentServiceStub(channel)


# ── Session state ─────────────────────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "session_id":  str(uuid.uuid4()),
        "messages":    [],
        "resume_text": "",
        "user_name":   "",
        "target_role": "",
        "target_city": "",
        "backend_ok":  None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session_state()


# ── gRPC helpers ──────────────────────────────────────────────────────────────

def check_backend() -> bool:
    """Probe the gRPC server with a HealthCheck RPC. Returns True if healthy."""
    try:
        resp = _get_stub().HealthCheck(
            job_agent_pb2.HealthRequest(),
            timeout=5,
        )
        return resp.status == "healthy"
    except Exception:
        return False


def send_message(message: str) -> str:
    """
    Send a message to the ChatPublic RPC and return the agent's reply.
    No authentication required.
    """
    try:
        resp = _get_stub().ChatPublic(
            job_agent_pb2.ChatRequest(
                message=message,
                session_id=st.session_state.session_id,
            ),
            timeout=REQUEST_TIMEOUT,
        )
        return resp.response or "No response received."

    except grpc.RpcError as exc:
        code = exc.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            return (
                "The request timed out. The agent may be processing a complex "
                "query. Please try again or rephrase your question."
            )
        if code == grpc.StatusCode.UNAVAILABLE:
            return (
                f"Could not connect to the gRPC server at "
                f"`{GRPC_HOST}:{GRPC_PORT}`. "
                "Please ensure the backend server is running:\n"
                "```\ncd src/backend\npython main.py\n```"
            )
        if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            return "The AI service is currently rate-limited. Please wait a moment and try again."
        return f"gRPC error [{code.name}]: {exc.details()}"

    except Exception as exc:
        return f"An unexpected error occurred: {exc}"


def new_chat() -> None:
    """Reset the local conversation state and start a fresh backend session."""
    st.session_state.messages   = []
    st.session_state.session_id = str(uuid.uuid4())


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💼 Job Placement Agent")
    st.markdown("_Your AI-powered career assistant_")
    st.markdown("---")

    # Backend status
    if st.session_state.backend_ok is None:
        st.session_state.backend_ok = check_backend()

    status_icon = "🟢" if st.session_state.backend_ok else "🔴"
    status_text = "gRPC server connected" if st.session_state.backend_ok else "gRPC server offline"
    st.markdown(f"{status_icon} {status_text}")

    if not st.session_state.backend_ok:
        st.warning(
            f"Start the gRPC backend:\n"
            f"```\ncd src/backend\npython main.py\n```\n"
            f"_(listening on {GRPC_HOST}:{GRPC_PORT})_"
        )

    st.markdown("---")

    # ── User info ──────────────────────────────────────────────────────────────
    st.markdown("### 👤 Your Information")
    user_name = st.text_input("Full Name",
        value=st.session_state.user_name, placeholder="e.g. Jane Smith")
    if user_name != st.session_state.user_name:
        st.session_state.user_name = user_name

    target_role = st.text_input("Target Role",
        value=st.session_state.target_role, placeholder="e.g. Data Engineer")
    if target_role != st.session_state.target_role:
        st.session_state.target_role = target_role

    target_city = st.text_input("Preferred Location",
        value=st.session_state.target_city, placeholder="e.g. New York, Remote")
    if target_city != st.session_state.target_city:
        st.session_state.target_city = target_city

    st.markdown("---")

    # ── Resume ─────────────────────────────────────────────────────────────────
    st.markdown("### 📄 Your Resume")
    resume_text = st.text_area(
        "Paste resume text here",
        value=st.session_state.resume_text,
        height=220,
        placeholder=(
            "Copy and paste your full resume here.\n\n"
            "The agent will use it to:\n"
            "• Analyze your skills\n"
            "• Find matching jobs\n"
            "• Write tailored cover letters"
        ),
    )
    if resume_text != st.session_state.resume_text:
        st.session_state.resume_text = resume_text

    if st.session_state.resume_text:
        st.success(f"Resume loaded ({len(st.session_state.resume_text):,} characters)")

    st.markdown("---")

    # ── Session management ─────────────────────────────────────────────────────
    st.markdown("### ⚙️ Session")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 New Chat", use_container_width=True):
            new_chat()
            st.rerun()

    with col2:
        if st.button("🔃 Retry", use_container_width=True):
            st.session_state.backend_ok = check_backend()
            st.rerun()

    st.caption(f"Session: `{st.session_state.session_id[:8]}…`")
    st.caption(f"Transport: gRPC `{GRPC_HOST}:{GRPC_PORT}`")


# ── Main layout ───────────────────────────────────────────────────────────────
st.markdown(
    '<p class="agent-title">💼 Job Placement Agent</p>'
    '<p class="agent-subtitle">Your AI-powered career assistant — '
    "find jobs, analyze your resume, and craft cover letters.</p>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Quick-action buttons ──────────────────────────────────────────────────────
st.markdown("**Quick Actions:**")
qa_cols = st.columns(4)


def _quick_action_prompt(label: str) -> str:
    name   = st.session_state.user_name or "there"
    role   = st.session_state.target_role
    city   = st.session_state.target_city
    resume = st.session_state.resume_text

    if "Find Jobs" in label:
        if role and city:
            return f"Find me {role} jobs in {city}"
        if role:
            return f"Find me {role} job openings"
        return "Help me find relevant job listings. What information do you need?"

    if "Analyze" in label:
        if resume:
            base = "Please analyze my resume"
            if role:
                base += f" and compare it to {role} job requirements"
            return base
        return "I'd like you to analyze my resume. How should I share it with you?"

    if "Cover Letter" in label:
        if resume and role:
            return (
                f"Generate a cover letter for a {role} position"
                + (f" in {city}" if city else "")
            )
        return "Help me write a cover letter. What details do you need?"

    if "Career Tips" in label:
        if role:
            return f"What are the top skills and career tips for a {role} role in {city or 'the current market'}?"
        return "What are the most in-demand tech skills in the current job market?"

    return label


quick_actions = ["🔍 Find Jobs", "📊 Analyze Resume", "✉️ Cover Letter", "💡 Career Tips"]
for i, label in enumerate(quick_actions):
    with qa_cols[i]:
        if st.button(label, use_container_width=True, key=f"qa_{i}"):
            st.session_state["_quick_prompt"] = _quick_action_prompt(label)


# ── Chat message display ──────────────────────────────────────────────────────
st.markdown("### 💬 Conversation")

with st.container():
    if not st.session_state.messages:
        welcome_name = f", {st.session_state.user_name}" if st.session_state.user_name else ""
        st.markdown(
            f"""
            <div class="chat-assistant">
            👋 Hello{welcome_name}! I'm your <strong>Job Placement Agent</strong>.<br><br>
            I can help you:<br>
            🔍 <strong>Find relevant job listings</strong> — just tell me your role and city<br>
            📊 <strong>Analyze your resume</strong> — paste it in the sidebar<br>
            🎯 <strong>Identify skill gaps</strong> — compare your skills to job requirements<br>
            ✉️  <strong>Write cover letters</strong> — tailored to any specific job<br><br>
            What would you like to start with?
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                with st.container():
                    st.markdown('<div class="chat-assistant">', unsafe_allow_html=True)
                    st.markdown(msg["content"])
                    st.markdown("</div>", unsafe_allow_html=True)


# ── Handle quick-action prompt ────────────────────────────────────────────────
if "_quick_prompt" in st.session_state and st.session_state["_quick_prompt"]:
    prompt = st.session_state.pop("_quick_prompt")
    st.session_state.messages.append({"role": "user", "content": prompt})

    enriched = prompt
    if st.session_state.resume_text and "my resume" not in prompt.lower():
        enriched = (
            f"{prompt}\n\n[Context — My Resume]:\n{st.session_state.resume_text[:3000]}"
        )

    with st.spinner("Agent is thinking…"):
        response = send_message(enriched)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()


# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Ask me about jobs, share your resume, request a cover letter…"
)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    enriched_input = user_input
    if (
        st.session_state.resume_text
        and "resume" in user_input.lower()
        and "[context" not in user_input.lower()
    ):
        enriched_input = (
            f"{user_input}\n\n[Context — My Resume]:\n"
            f"{st.session_state.resume_text[:3000]}"
        )

    with st.spinner("Agent is thinking…"):
        response = send_message(enriched_input)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<center><small>Job Placement Agent • Built with LangChain, gRPC &amp; Streamlit • "
    "Powered by Gemini via OpenAI-compatible API</small></center>",
    unsafe_allow_html=True,
)
