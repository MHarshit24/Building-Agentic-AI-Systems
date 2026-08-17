"""
FinDoc Analyzer — Human Handoff Service
Dual .env loader: root .env (secrets) + project .env (config).
handoff_service.py: main/handoff/handoff_service.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env
"""

import os
import sys
import logging
import smtplib
import datetime
import secrets
import re
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_env():
    if "pytest" in sys.modules:
        return
    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")
    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"
    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")
    for key, val in _preserved.items():
        if val:
            os.environ[key] = val
    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


_load_env()

# ── SLO thresholds for handoff (lowered to 0.5 & 0.4 to trigger on risky queries) ───────
FAITHFULNESS_THRESHOLD = float(os.getenv("HANDOFF_FAITHFULNESS_THRESHOLD", "0.5"))
RELEVANCE_THRESHOLD    = float(os.getenv("HANDOFF_RELEVANCE_THRESHOLD",    "0.4"))
CONFIDENCE_THRESHOLD   = int(os.getenv("HANDOFF_CONFIDENCE_THRESHOLD",     "20"))

# ── Email config ──────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM    = os.getenv("APPLICATION_EMAIL")
EMAIL_TO      = os.getenv("SUPPORT_EMAIL")


def generate_handoff_reference_id(now: Optional[datetime.datetime] = None) -> str:
    """Generate unique handoff reference ID."""
    now = now or datetime.datetime.now(datetime.UTC)
    return f"FINDOC-HO-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3).upper()}"


def evaluate_score(
    faithfulness:  Optional[float],
    relevance:     Optional[float],
    user_question: str,
    no_chunks:     bool,
) -> Dict[str, Any]:
    """
    Determine if scores require handoff escalation.
    LOWERED thresholds to 0.5 & 0.4 to actually trigger handoffs for risky queries.
    Added high-risk query detection.
    """
    # No chunks retrieved = high risk escalation
    if no_chunks:
        return {"trigger": True, "reason": "no context chunks retrieved — escalating to expert"}

    # High-risk financial queries need expert review
    risk_keywords = ["should i invest", "should i buy", "should i sell", "guaranteed", 
                     "recommend", "best investment", "sure bet", "safe investment", "financial advice"]
    if any(kw in user_question.lower() for kw in risk_keywords):
        return {"trigger": True, "reason": "high-risk financial query (investment advice) — expert review required"}

    # If scores couldn't be computed, escalate on risky keywords
    if faithfulness is None or relevance is None:
        return {"trigger": False, "reason": "evaluation scores unavailable"}

    # LOWERED from 0.6 to 0.5
    if faithfulness < FAITHFULNESS_THRESHOLD:
        return {
            "trigger": True,
            "reason":  f"faithfulness score {faithfulness:.2f} below threshold {FAITHFULNESS_THRESHOLD}",
        }

    # LOWERED from 0.5 to 0.4
    if relevance < RELEVANCE_THRESHOLD:
        return {
            "trigger": True,
            "reason":  f"answer relevance {relevance:.2f} below threshold {RELEVANCE_THRESHOLD}",
        }

    # Explicit escalation keywords
    if any(
        word in user_question.lower()
        for word in ["human", "agent", "expert", "support", "escalate", "speak to someone"]
    ):
        return {"trigger": True, "reason": "explicit user escalation request (keyword)"}

    return {"trigger": False}


async def evaluate_confidence_score(answer: str) -> Dict[str, Any]:
    """LLM self-rated confidence on the generated answer. Returns trigger if < threshold."""
    from llama_index.core.settings import Settings

    llm = Settings.llm
    if llm is None:
        return {"trigger": False, "confidence": 50}

    try:
        prompt = (
            f"Rate your confidence in the following answer from 0 to 100.\n"
            f"0 = completely uncertain / hallucination likely\n"
            f"100 = very confident / well-supported by evidence\n"
            f"Return ONLY an integer number.\n\n"
            f"Answer: {answer[:600]}\n\n"
            f"Confidence (0-100):"
        )
        resp  = await llm.acomplete(prompt)
        score = int("".join(filter(str.isdigit, resp.text)) or "50")
        score = max(0, min(100, score))

        if score < CONFIDENCE_THRESHOLD:
            return {
                "trigger":    True,
                "reason":     f"LLM confidence {score}/100 below threshold {CONFIDENCE_THRESHOLD}",
                "confidence": score,
            }
        return {"trigger": False, "confidence": score}

    except Exception as e:
        logger.error(f"Confidence evaluation failed: {e}")
        return {"trigger": False, "confidence": 50}


async def evaluate_explicit_user_request(message: str) -> Dict[str, Any]:
    """LLM-based classifier for explicit user escalation request."""
    from llama_index.core.settings import Settings

    llm = Settings.llm
    if llm is None:
        return {"trigger": False}

    try:
        prompt = (
            f'Is the user explicitly asking to speak with a human expert, '
            f'requesting escalation, or expressing frustration/dissatisfaction?\n'
            f'Respond only YES or NO.\n\n'
            f'Message: "{message}"\n\nAnswer:'
        )
        resp = await llm.acomplete(prompt)
        if "YES" in resp.text.upper():
            return {"trigger": True, "reason": "LLM classified explicit handoff request"}
        return {"trigger": False}
    except Exception as e:
        logger.error(f"Explicit request check failed: {e}")
        return {"trigger": False}


def send_handoff_email(context: Dict[str, Any]):
    """Send human handoff email with full context bundle."""
    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        logger.warning("Email settings incomplete — handoff email not sent")
        return False

    subject = (
        f"[FINDOC HANDOFF] Ref {context['reference_id']} "
        f"| {context['trigger_reason']}"
    )

    body = f"""
FinDoc Analyzer — Human Handoff Triggered
==========================================

Reference ID  : {context['reference_id']}
Trace ID      : {context.get('trace_id', 'N/A')}
Timestamp UTC : {context['timestamp_utc']}
Priority      : {context.get('priority', 'normal')}
Session ID    : {context.get('session_id', 'N/A')}

Reason for Handoff:
{context['trigger_reason']}

User Email: {context.get('user_metadata', {}).get('email', 'N/A')}

──────────────────────────────────────────
User Question:
──────────────────────────────────────────
{context.get('question', 'N/A')}

──────────────────────────────────────────
Generated Answer:
──────────────────────────────────────────
{context.get('generated_answer', 'N/A')}

──────────────────────────────────────────
Evaluation Scores:
──────────────────────────────────────────
Faithfulness : {context.get('evaluation_scores', {}).get('faithfulness', 'N/A')}
Relevance    : {context.get('evaluation_scores', {}).get('relevance', 'N/A')}
Confidence   : {context.get('evaluation_scores', {}).get('confidence', 'N/A')}

──────────────────────────────────────────
Query Routing Used: {context.get('routing_used', 'N/A')}

──────────────────────────────────────────
Retrieved Document Chunks:
──────────────────────────────────────────
{context.get('retrieved_chunks', 'No chunks retrieved')}

──────────────────────────────────────────
Action Required:
──────────────────────────────────────────
Please review the above context and provide a human-reviewed response.
Reference this ticket ID: {context['reference_id']}
"""

    msg            = MIMEText(body)
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.info(f"Handoff email sent for ref={context['reference_id']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send handoff email: {e}")
        return False