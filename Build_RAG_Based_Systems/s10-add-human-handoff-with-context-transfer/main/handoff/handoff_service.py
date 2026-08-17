import os
import sys
import logging
import smtplib
import datetime
import secrets
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from llama_index.core.settings import Settings


logger = logging.getLogger(__name__)

FAITHFULNESS_THRESHOLD = 0.6
RELEVANCE_THRESHOLD = 0.5
CONFIDENCE_THRESHOLD = 40


def _load_env():
    """
    Load environment variables preserving secrets from root .env,
    then loading project .env with override.

    - Root .env (Building_Agentic_AI_Systems/.env) loaded first for secrets.
    - Project .env loaded second with override=True.
    - Secrets restored after second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # Locate root .env (Building_Agentic_AI_Systems/.env)
    # This file: <project>/main/handoff/handoff_service.py -> parents[4] = root
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}, falling back to default load_dotenv()")

    # Preserve secret values before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    application_email = os.getenv("APPLICATION_EMAIL")
    support_email = os.getenv("SUPPORT_EMAIL")

    # Locate project .env (s10 project root/.env)
    # This file: <project>/main/handoff/handoff_service.py -> parents[2] = project root
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logger.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}, falling back to default load_dotenv()")

    # Restore preserved secrets so project .env cannot overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
    if llama_cloud_api_key:
        os.environ["LLAMA_CLOUD_API_KEY"] = llama_cloud_api_key
    if langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
    if langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key
    if langfuse_host:
        os.environ["LANGFUSE_HOST"] = langfuse_host
    if smtp_host:
        os.environ["SMTP_HOST"] = smtp_host
    if smtp_port:
        os.environ["SMTP_PORT"] = smtp_port
    if smtp_username:
        os.environ["SMTP_USERNAME"] = smtp_username
    if smtp_password:
        os.environ["SMTP_PASSWORD"] = smtp_password
    if application_email:
        os.environ["APPLICATION_EMAIL"] = application_email
    if support_email:
        os.environ["SUPPORT_EMAIL"] = support_email

    # Remove conflicting PostgreSQL variables that may come from root .env
    conflicting_pg_vars = [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)


# Load env on module import so SMTP_* vars are available at module level
_load_env()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("APPLICATION_EMAIL")
EMAIL_TO = os.getenv("SUPPORT_EMAIL")


def generate_handoff_reference_id(now: Optional[datetime.datetime] = None) -> str:
    """Generate a unique handoff reference ID in format: HO-YYYYMMDD-HHMMSS-HEXCODE"""
    # TODO: Generate ID with current UTC time (if now is None) + 3-byte hex token
    # Format: f"HO-{timestamp}-{secrets.token_hex(3).upper()}"
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    hex_code = secrets.token_hex(3).upper()
    return f"HO-{timestamp}-{hex_code}"


def evaluate_score(
    faithfulness: Optional[float],
    relevance: Optional[float],
    user_question: str,
    no_chunks: bool
) -> Dict[str, Any]:
    """Determines if the system should escalate based on evaluation scores."""
    # TODO: Check triggers in order and return {"trigger": bool, "reason": str}:
    # 1. no_chunks → "retrieval returned no context"
    # 2. faithfulness or relevance is None → "evaluation scores unavailable"
    # 3. faithfulness < 0.6 → "faithfulness below threshold"
    # 4. relevance < 0.5 → "answer relevance below threshold"
    # 5. Keywords in question (human/agent/support/escalate) → "explicit user request"
    # 6. Otherwise → {"trigger": False}
    if no_chunks:
        return {"trigger": True, "reason": "retrieval returned no context"}

    if faithfulness is None or relevance is None:
        return {"trigger": True, "reason": "evaluation scores unavailable"}

    if faithfulness < FAITHFULNESS_THRESHOLD:
        return {"trigger": True, "reason": "faithfulness below threshold"}

    if relevance < RELEVANCE_THRESHOLD:
        return {"trigger": True, "reason": "answer relevance below threshold"}

    keywords = ["human", "agent", "support", "escalate"]
    question_lower = user_question.lower()
    if any(kw in question_lower for kw in keywords):
        return {"trigger": True, "reason": "explicit user request"}

    return {"trigger": False, "reason": ""}


async def evaluate_confidence_score(answer: str) -> Dict[str, Any]:
    """Evaluate LLM confidence score (0-100) and trigger handoff if below threshold (40)."""
    # TODO: Use LLM to rate confidence
    # 1. Get Settings.llm (raise ValueError if None)
    # 2. Prompt: "Rate confidence 0–100.\nAnswer: {answer}"
    # 3. Parse score from response (extract digits, default to 50)
    # 4. Return {"trigger": bool, "reason": str, "confidence": int}
    llm = Settings.llm
    if llm is None:
        logger.warning(
            "Settings.llm is not initialized. "
            "Returning default confidence result."
        )
        return {
            "trigger": False,
            "reason": "confidence evaluator unavailable",
            "confidence": 50,
        }
    prompt = (
        "You are evaluating the confidence of an AI-generated answer.\n"
        "Rate how confident the answer appears to be on a scale of 0 to 100.\n"
        "0 = completely uncertain or refusing to answer, "
        "100 = highly confident and definitive.\n"
        "Respond with ONLY a single integer number between 0 and 100.\n\n"
        f"Answer: {answer}"
    )

    try:
        response = llm.complete(prompt)
        response_text = response.text.strip()
        # Extract digits from response, default to 50 if parsing fails
        import re
        digits = re.findall(r'\d+', response_text)
        score = int(digits[0]) if digits else 50
        # Clamp to valid range
        score = max(0, min(100, score))
    except Exception as e:
        logger.warning(f"Confidence score parsing failed: {e}, defaulting to 50")
        score = 50

    trigger = score < CONFIDENCE_THRESHOLD
    reason = "low confidence score" if trigger else ""
    return {"trigger": trigger, "reason": reason, "confidence": score}


async def evaluate_explicit_user_request(message: str) -> Dict[str, Any]:
    """LLM-based classifier for explicit user request or frustration."""
    # TODO: Use LLM to classify if user is asking for human help
    # 1. Get Settings.llm (raise ValueError if None)
    # 2. Prompt: Ask LLM to return "YES" or "NO" if user wants human help
    # 3. Check if "YES" in response.text.upper()
    # 4. Return {"trigger": bool, "reason": str}
    llm = Settings.llm
    if llm is None:
        logger.warning(
            "Settings.llm is not initialized. "
            "Skipping explicit user request classification."
        )
        return {
            "trigger": False,
            "reason": ""
        }

    prompt = (
        "You are a classifier that detects if a user is explicitly requesting "
        "to speak with a human agent or support representative.\n\n"
        "Respond with ONLY 'YES' or 'NO'.\n"
        "YES = the user is explicitly asking for a human, agent, or support person, "
        "or expressing strong frustration that implies they want to escalate.\n"
        "NO = the user is simply asking a question or seeking information.\n\n"
        f"User message: {message}"
    )

    try:
        response = llm.complete(prompt)
        response_text = response.text.strip().upper()
        triggered = "YES" in response_text
    except Exception as e:
        logger.warning(f"Explicit user request classification failed: {e}, defaulting to no trigger")
        triggered = False

    if triggered:
        return {"trigger": True, "reason": "user explicitly requested human assistance"}
    return {"trigger": False, "reason": ""}


def send_handoff_email(context: Dict[str, Any]):
    """Send human handoff email via SMTP with full context."""
    # TODO: Implement email sending
    # 1. Check SMTP config (SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO)
    # 2. Build subject: "[HUMAN HANDOFF] Ref {reference_id} – {trigger_reason}"
    # 3. Build body with all context fields (reference_id, trace_id, timestamp, priority,
    #    trigger_reason, user_metadata, query_history, generated_answer, evaluation_scores,
    #    retrieved_chunks, conversation_flow)
    # 4. Create MIMEText message and set headers
    # 5. Send via SMTP with TLS (use try/except, log errors)

    # Re-read SMTP config from environment at call time to pick up any late-loaded values
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("APPLICATION_EMAIL")
    email_to = os.getenv("SUPPORT_EMAIL")

    # 1. Check all required SMTP configuration variables
    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_username:
        missing.append("SMTP_USERNAME")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not email_from:
        missing.append("APPLICATION_EMAIL")
    if not email_to:
        missing.append("SUPPORT_EMAIL")

    if missing:
        logger.warning(
            f"Handoff email not sent — missing SMTP configuration: {', '.join(missing)}"
        )
        return

    reference_id = context.get("reference_id", "N/A")
    trace_id = context.get("trace_id", "N/A")
    timestamp = context.get("timestamp", "N/A")
    priority = context.get("priority", "normal")
    trigger_reason = context.get("trigger_reason", "N/A")
    user_metadata = context.get("user_metadata", {})
    query_history = context.get("query_history", [])
    generated_answer = context.get("generated_answer", "N/A")
    evaluation_scores = context.get("evaluation_scores", {})
    retrieved_chunks = context.get("retrieved_chunks", [])
    conversation_flow = context.get("conversation_flow", [])

    # 2. Build subject
    subject = f"[HUMAN HANDOFF] Ref {reference_id} – {trigger_reason}"

    # 3. Build body with all context fields
    chunks_text = ""
    for i, chunk in enumerate(retrieved_chunks, 1):
        chunks_text += f"\n  Chunk {i}:\n  {chunk}\n"
    if not chunks_text:
        chunks_text = "\n  No chunks retrieved.\n"

    query_history_text = ""
    for i, q in enumerate(query_history, 1):
        query_history_text += f"\n  [{i}] {q}"
    if not query_history_text:
        query_history_text = "\n  No query history available."

    conversation_flow_text = ""
    for step in conversation_flow:
        conversation_flow_text += f"\n  - {step}"
    if not conversation_flow_text:
        conversation_flow_text = "\n  No conversation flow recorded."

    body = f"""
========================================================
HUMAN HANDOFF NOTIFICATION
========================================================

Reference ID     : {reference_id}
Trace ID         : {trace_id}
Timestamp        : {timestamp}
Priority         : {priority.upper()}
Trigger Reason   : {trigger_reason}

--------------------------------------------------------
USER METADATA
--------------------------------------------------------
{chr(10).join(f'  {k}: {v}' for k, v in user_metadata.items()) if user_metadata else '  No user metadata available.'}

--------------------------------------------------------
QUERY HISTORY
--------------------------------------------------------
{query_history_text}

--------------------------------------------------------
GENERATED ANSWER
--------------------------------------------------------
  {generated_answer}

--------------------------------------------------------
EVALUATION SCORES
--------------------------------------------------------
  Faithfulness    : {evaluation_scores.get('faithfulness', 'N/A')}
  Answer Relevance: {evaluation_scores.get('relevance', 'N/A')}
  Confidence      : {evaluation_scores.get('confidence', 'N/A')}

--------------------------------------------------------
RETRIEVED CHUNKS
--------------------------------------------------------
{chunks_text}
--------------------------------------------------------
CONVERSATION FLOW
--------------------------------------------------------
{conversation_flow_text}

========================================================
Please follow up with the user at your earliest convenience.
========================================================
"""

    # 4. Create MIMEText message and set headers
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    # 5. Send via SMTP with STARTTLS
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, email_to, msg.as_string())
        logger.info(f"✓ Handoff email sent successfully — Ref: {reference_id}")
    except Exception as e:
        logger.error(f"Failed to send handoff email (Ref: {reference_id}): {e}", exc_info=True)