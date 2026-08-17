"""
Resume Analyzer Tool
--------------------
Extracts skills, assesses experience level, and identifies skill gaps using
the Gemini LLM.

Public API
~~~~~~~~~~
``analyze_resume_core(resume_text, job_description)``
    Core function — raises ``GeminiError`` subclasses on LLM failure.
    Used by the direct REST endpoint ``POST /api/resume/analyze``.

``analyze_resume`` (LangChain @tool)
    Thin wrapper — returns a human-readable error string on failure.
    Used only by the AgentExecutor inside the chat flow.

LCEL Pattern (Sprint 5/6)
~~~~~~~~~~~~~~~~~~~~~~~~~
This tool uses the explicit LCEL pipe syntax to build the LLM chain:

    chain = prompt_template | llm | StrOutputParser()

instead of calling ``invoke_llm()`` directly.  This demonstrates:
  - ChatPromptTemplate as the input stage
  - LLM as the transform stage
  - StrOutputParser as the output stage
"""
import logging
from functools import lru_cache

from langchain.tools import tool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from exceptions import GeminiError

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_ANALYSIS_PROMPT = """You are an expert career consultant and resume reviewer.

Analyze the following resume and provide a comprehensive, structured assessment.

== RESUME ==
{resume}

{job_section}

## Provide the following sections:

### 1. Professional Summary
Brief overview of the candidate's background and career trajectory.

### 2. Technical Skills Extracted
List all technical skills, tools, frameworks, and technologies found in the resume.

### 3. Soft Skills Identified
Communication, leadership, teamwork, and other soft skills evident from the resume.

### 4. Experience Level Assessment
- Career level: (Entry / Junior / Mid / Senior / Lead / Principal / Executive)
- Total estimated years of experience
- Primary domain/industry expertise

### 5. Education & Certifications
Degrees, certifications, and notable courses.

{gap_section}

### {next_section_number}. Resume Improvement Suggestions
Provide 5-7 specific, actionable recommendations to strengthen this resume:
- Use metrics where possible (e.g., "increased throughput by 30%")
- Highlight missing sections or weak areas
- Suggest keywords or technologies to add

### {final_section_number}. Overall Resume Score
Rate the resume out of 10 and justify the score.

Be direct, specific, and constructive. Avoid generic advice."""

_JOB_SECTION_TEMPLATE = """== JOB DESCRIPTION ==
{job_description}
"""

_GAP_SECTION_TEMPLATE = """### {section_num}. Skill Gap Analysis (vs. Job Description)
- Matching skills: List skills in the resume that directly match the job requirements
- Missing critical skills: Skills required by the job not found in the resume
- Skills to improve: Present but needs deepening
- Estimated match score: X% (with brief rationale)
- Top 3 skills to acquire first to become a stronger candidate
"""


# ── LCEL chain (Sprint 5/6: pipe syntax) ─────────────────────────────────────
# chain = prompt_template | llm | StrOutputParser()
# Built lazily (lru_cache) so env vars are available before first use.

@lru_cache(maxsize=1)
def _get_analysis_chain():
    """
    Build the resume-analysis LCEL chain.

    Pipeline:
        ChatPromptTemplate  →  Gemini LLM  →  StrOutputParser
              (format)              (generate)       (extract .content)

    Demonstrates Sprint 5/6 LCEL pipe (|) syntax.
    """
    prompt_template = ChatPromptTemplate.from_messages(
        [("human", "{analysis_prompt}")]
    )
    return prompt_template | get_llm() | StrOutputParser()


# ── Core function (raises on error) ──────────────────────────────────────────

def analyze_resume_core(resume_text: str, job_description: str = "", callbacks: list | None = None) -> str:
    """
    Analyze a resume using the Gemini LLM.

    This is the **core function** consumed by the direct REST endpoint
    ``POST /api/resume/analyze``. It raises domain exceptions on failure.

    Args:
        resume_text:     Full text of the candidate's resume (min 50 chars).
        job_description: Optional job description for gap analysis.

    Returns:
        Structured analysis as a markdown string.

    Raises:
        ValueError:            resume_text is too short.
        GeminiConfigError:     Gemini API key missing / invalid.
        GeminiRateLimitError:  Gemini rate limit exceeded.
        GeminiNetworkError:    Gemini unreachable.
        GeminiError:           Any other LLM failure.
    """
    if not resume_text or len(resume_text.strip()) < 50:
        raise ValueError(
            "resume_text is too short to analyze (minimum 50 characters). "
            "Please paste the full content of your resume."
        )

    # Build prompt sections dynamically based on whether a JD was supplied
    if job_description and len(job_description.strip()) > 20:
        job_section = _JOB_SECTION_TEMPLATE.format(job_description=job_description)
        gap_section = _GAP_SECTION_TEMPLATE.format(section_num=6)
        next_num    = 7
        final_num   = 8
    else:
        job_section = ""
        gap_section = ""
        next_num    = 6
        final_num   = 7

    prompt = _ANALYSIS_PROMPT.format(
        resume=resume_text,
        job_section=job_section,
        gap_section=gap_section,
        next_section_number=next_num,
        final_section_number=final_num,
    )

    logger.info(
        "analyze_resume_core — resume_len=%d, has_jd=%s",
        len(resume_text),
        bool(job_description),
    )

    # ── LCEL pipe: prompt_template | llm | StrOutputParser() ─────────────────
    # Sprint 5/6: explicit chain composition with the pipe (|) operator.
    chain = _get_analysis_chain()
    invoke_config = {"callbacks": callbacks} if callbacks else {}
    return chain.invoke({"analysis_prompt": prompt}, config=invoke_config)


# ── LangChain tool (used by the AgentExecutor) ────────────────────────────────

@tool
def analyze_resume(resume_text: str, job_description: str = "") -> str:
    """
    Analyze a resume to extract skills, assess experience level, and identify skill gaps.

    Use this tool when:
    - The user shares their resume text
    - The user asks what skills they have
    - The user wants to know how well they match a job description
    - The user requests career improvement suggestions

    Args:
        resume_text:     The full text of the user's resume (required)
        job_description: Optional job description to compare against for gap analysis

    Returns:
        Structured analysis including extracted skills, experience level, gaps, and
        improvement tips — or an error message the LLM can communicate to the user.
    """
    logger.info(
        "analyze_resume tool — resume_len=%d, has_jd=%s",
        len(resume_text),
        bool(job_description),
    )
    try:
        return analyze_resume_core(resume_text, job_description)
    except ValueError as exc:
        return str(exc)
    except GeminiError as exc:
        logger.error("%s in analyze_resume tool: %s", type(exc).__name__, exc)
        return (
            "I encountered an issue analyzing your resume with the AI service. "
            f"Details: {exc}. Please try again in a moment."
        )
    except Exception as exc:
        logger.error("Unexpected error in analyze_resume tool: %s", exc, exc_info=True)
        return (
            "An unexpected error occurred while analyzing your resume. "
            "Please try again."
        )
