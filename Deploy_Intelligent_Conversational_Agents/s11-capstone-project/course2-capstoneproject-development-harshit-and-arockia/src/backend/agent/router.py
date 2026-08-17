"""
Intent Router — LCEL RunnableBranch for Conditional Workflow Dispatch
----------------------------------------------------------------------
Sprint 5/6: Router Chains for Conditional Workflows.

Architecture
~~~~~~~~~~~~
    user query
        │
        ▼
    classify_chain   ← ChatPromptTemplate | LLM | StrOutputParser
        │
        ▼  intent label  ("job_search" | "resume_analysis" | "cover_letter" | "general")
        │
        ▼
    RunnableBranch
        ├─ job_search     → job_search_chain     (ChatPromptTemplate | LLM | StrOutputParser)
        ├─ resume_analysis → resume_chain        (ChatPromptTemplate | LLM | StrOutputParser)
        ├─ cover_letter   → cover_letter_chain   (ChatPromptTemplate | LLM | StrOutputParser)
        └─ (default)      → general_chain        (ChatPromptTemplate | LLM | StrOutputParser)

Every stage uses the LCEL pipe (|) operator — each segment is a Runnable
composed with the next via the | operator:

    chain = prompt_template | llm | StrOutputParser()

The router itself is composed with:

    full_pipeline = RunnablePassthrough.assign(intent=classify_chain) | branch

Public API
~~~~~~~~~~
``get_router_pipeline()``  — returns the cached full pipeline (lazy-built).
``route_query(query)``     — classify + respond; returns (intent_label, response).
"""

import logging
from functools import lru_cache
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBranch, RunnablePassthrough

from agent.llm import get_llm

logger = logging.getLogger(__name__)

# ── Intent labels ──────────────────────────────────────────────────────────────

INTENT_JOB_SEARCH   = "job_search"
INTENT_RESUME       = "resume_analysis"
INTENT_COVER_LETTER = "cover_letter"
INTENT_GENERAL      = "general"

# ── Prompt templates ───────────────────────────────────────────────────────────

_CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an intent classifier for a job placement assistant.\n"
        "Classify the user message into exactly one of these categories:\n"
        "  job_search      — user wants to find or browse job listings\n"
        "  resume_analysis — user wants resume feedback, skill extraction, or gap analysis\n"
        "  cover_letter    — user wants a cover letter written for a job application\n"
        "  general         — greeting, follow-up question, or anything else\n\n"
        "Reply with ONLY the category name — no explanation, no punctuation, no extra words.",
    ),
    ("human", "{query}"),
])

_JOB_SEARCH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a job search advisor for a career placement assistant.\n"
        "Give concise, actionable guidance for finding relevant job opportunities.\n"
        "Focus on job titles, locations, skills, and where to search.",
    ),
    ("human", "{query}"),
])

_RESUME_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a professional resume coach.\n"
        "Provide structured, actionable feedback on resume content, skills, and presentation.\n"
        "Be specific — highlight strengths and concrete improvements.",
    ),
    ("human", "{query}"),
])

_COVER_LETTER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert cover letter writer.\n"
        "Provide targeted writing advice, structure tips, and tone guidance.\n"
        "Help the user craft a compelling, personalized application letter.",
    ),
    ("human", "{query}"),
])

_GENERAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a friendly, knowledgeable job placement assistant.\n"
        "Answer clearly and helpfully. Guide the user toward relevant features "
        "(job search, resume review, or cover letter) when appropriate.",
    ),
    ("human", "{query}"),
])


# ── Chain factory (lazy, cached) ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_classify_chain():
    """
    Classification chain — Sprint 5/6 LCEL pipe syntax:
        ChatPromptTemplate | LLM | StrOutputParser
    """
    return _CLASSIFY_PROMPT | get_llm() | StrOutputParser()


@lru_cache(maxsize=1)
def get_router_pipeline():
    """
    Build and return the full intent-router pipeline (cached after first call).

    Pipeline (Sprint 5/6 — Router Chains):

        RunnablePassthrough.assign(intent=classify_chain)   ← adds intent key
            |
        RunnableBranch(                                      ← routes on intent
            (job_search,    job_search_chain),
            (resume,        resume_chain),
            (cover_letter,  cover_letter_chain),
            general_chain,                                   ← default
        )

    Each branch chain is:  ChatPromptTemplate | LLM | StrOutputParser

    Args:
        None — uses the cached LLM instance from ``agent.llm.get_llm()``.

    Returns:
        A Runnable that accepts ``{"query": str}`` and returns a response str.
    """
    llm    = get_llm()
    parser = StrOutputParser()

    # ── Per-intent response chains (LCEL pipe syntax) ─────────────────────────
    job_search_chain    = _JOB_SEARCH_PROMPT    | llm | parser
    resume_chain        = _RESUME_PROMPT        | llm | parser
    cover_letter_chain  = _COVER_LETTER_PROMPT  | llm | parser
    general_chain       = _GENERAL_PROMPT       | llm | parser

    # ── Branch: routes on the "intent" key injected by assign() ───────────────
    branch = RunnableBranch(
        (lambda x: INTENT_JOB_SEARCH   in x.get("intent", ""), job_search_chain),
        (lambda x: INTENT_RESUME       in x.get("intent", ""), resume_chain),
        (lambda x: INTENT_COVER_LETTER in x.get("intent", ""), cover_letter_chain),
        general_chain,  # default — catches INTENT_GENERAL and unknowns
    )

    # ── Full pipeline: classify → assign intent key → branch ──────────────────
    # RunnablePassthrough.assign(intent=classify_chain) enriches the input dict
    # with an "intent" key before passing it to the branch.
    classify_chain = _get_classify_chain()
    return RunnablePassthrough.assign(intent=classify_chain) | branch


# ── Public function ────────────────────────────────────────────────────────────

def route_query(
    query: str,
    callbacks: Optional[list] = None,
) -> tuple[str, str]:
    """
    Classify a user query and respond using the matching specialist chain.

    Runs two LLM calls:
      1. Classifier → intent label
      2. Specialist chain → natural-language response

    Args:
        query:     The user's message.
        callbacks: Optional LangChain callbacks (e.g. Langfuse handler).

    Returns:
        ``(intent_label, response_text)`` — both as plain strings.
    """
    config = {"callbacks": callbacks} if callbacks else {}

    # Step 1 — classify (separate call so we can return the label to the caller)
    intent = _get_classify_chain().invoke({"query": query}, config=config).strip()
    logger.info("route_query — intent='%s', query_len=%d", intent, len(query))

    # Step 2 — route through the branch (pass intent directly to skip re-classify)
    llm    = get_llm()
    parser = StrOutputParser()

    branch = RunnableBranch(
        (lambda x: INTENT_JOB_SEARCH   in x.get("intent", ""), _JOB_SEARCH_PROMPT    | llm | parser),
        (lambda x: INTENT_RESUME       in x.get("intent", ""), _RESUME_PROMPT        | llm | parser),
        (lambda x: INTENT_COVER_LETTER in x.get("intent", ""), _COVER_LETTER_PROMPT  | llm | parser),
        _GENERAL_PROMPT | llm | parser,
    )
    response = branch.invoke({"query": query, "intent": intent}, config=config)

    return intent, response
