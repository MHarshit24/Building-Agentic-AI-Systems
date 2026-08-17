"""
Cover Letter Generator Tool
----------------------------
Generates personalized, professional cover letters using the Gemini LLM.

Public API
~~~~~~~~~~
``generate_cover_letter_core(resume_text, job_title, company_name, job_description, user_name)``
    Core function — raises ``GeminiError`` subclasses on LLM failure.
    Used by the direct REST endpoint ``POST /api/cover-letter/generate``.

``generate_cover_letter`` (LangChain @tool)
    Thin wrapper — returns a human-readable error string on failure.
    Used only by the AgentExecutor inside the chat flow.
"""
import logging
from datetime import date

from langchain.tools import tool

from agent.llm import invoke_llm
from exceptions import GeminiError

logger = logging.getLogger(__name__)

# ── Prompt template ───────────────────────────────────────────────────────────

_COVER_LETTER_PROMPT = """You are an expert career writer specializing in professional cover letters.

Generate a compelling, personalized cover letter for the following job application.

== APPLICANT INFORMATION ==
Name: {user_name}
Resume / Background:
{resume_text}

== JOB DETAILS ==
Job Title: {job_title}
Company: {company_name}
Job Description:
{job_description}

Today's Date: {today}

== COVER LETTER REQUIREMENTS ==
1. **Opening paragraph** — Hook the reader immediately. Reference the specific role and show genuine enthusiasm for the company.
2. **Body paragraph 1** — Highlight the 2-3 most relevant experiences or accomplishments from the resume that directly match the job requirements. Use specific metrics or outcomes where possible.
3. **Body paragraph 2** — Demonstrate knowledge of the company/role and explain why the applicant is an exceptional fit culturally and professionally.
4. **Closing paragraph** — Confident, concise call-to-action. Express readiness to discuss further. Professional sign-off.

== STYLE GUIDELINES ==
- Professional yet personable tone — avoid stiff corporate language
- 3-4 paragraphs, 300-400 words total
- No generic phrases like "I am writing to apply for..." or "I believe I am a great fit"
- Start with a strong, attention-grabbing opening line
- Use the applicant's actual name throughout if appropriate
- Include proper date, salutation (Dear Hiring Manager / Dear [Company] Team), and closing

Generate ONLY the cover letter text — no preamble or explanation."""


# ── Core function (raises on error) ──────────────────────────────────────────

def generate_cover_letter_core(
    resume_text: str,
    job_title: str,
    company_name: str,
    job_description: str,
    user_name: str = "Applicant",
    callbacks: list | None = None,
) -> str:
    """
    Generate a personalized cover letter using the Gemini LLM.

    This is the **core function** consumed by the direct REST endpoint
    ``POST /api/cover-letter/generate``. It raises domain exceptions on failure.

    Args:
        resume_text:     The applicant's resume or career background.
        job_title:       Exact title of the role being applied for.
        company_name:    Name of the hiring company.
        job_description: Full or summarized job requirements.
        user_name:       Applicant's full name (default: "Applicant").

    Returns:
        A ready-to-use cover letter wrapped in a markdown header.

    Raises:
        ValueError:            Required inputs are missing or too short.
        GeminiConfigError:     Gemini API key missing / invalid.
        GeminiRateLimitError:  Gemini rate limit exceeded.
        GeminiNetworkError:    Gemini unreachable.
        GeminiError:           Any other LLM failure.
    """
    # Input validation
    missing = []
    if not resume_text or len(resume_text.strip()) < 30:
        missing.append("resume text (min 30 characters)")
    if not job_title or len(job_title.strip()) < 2:
        missing.append("job title")
    if not company_name or len(company_name.strip()) < 2:
        missing.append("company name")
    if not job_description or len(job_description.strip()) < 20:
        missing.append("job description (min 20 characters)")

    if missing:
        raise ValueError(
            f"Cannot generate a cover letter — missing required fields: {', '.join(missing)}."
        )

    prompt = _COVER_LETTER_PROMPT.format(
        user_name=user_name or "Applicant",
        resume_text=resume_text,
        job_title=job_title,
        company_name=company_name,
        job_description=job_description,
        today=date.today().strftime("%B %d, %Y"),
    )

    logger.info(
        "generate_cover_letter_core — job='%s' at '%s', user='%s'",
        job_title, company_name, user_name,
    )

    cover_letter = invoke_llm(prompt, callbacks=callbacks)

    return (
        f"## Cover Letter — {job_title} at {company_name}\n\n"
        f"{cover_letter}\n\n"
        "---\n"
        "_This cover letter is tailored to your resume and the job description. "
        "Feel free to ask me to adjust the tone, length, or emphasis on specific skills._"
    )


# ── LangChain tool (used by the AgentExecutor) ────────────────────────────────

@tool
def generate_cover_letter(
    resume_text: str,
    job_title: str,
    company_name: str,
    job_description: str,
    user_name: str = "Applicant",
) -> str:
    """
    Generate a personalized, professional cover letter for a job application.

    Use this tool when the user wants to apply for a specific job and needs
    a tailored cover letter. Ensure you have all required details before calling.

    Args:
        resume_text:     The user's resume or career background (required)
        job_title:       Exact job title being applied for (e.g. "Senior Data Engineer")
        company_name:    Name of the hiring company (e.g. "Google", "Acme Corp")
        job_description: Full or summarized job description / requirements
        user_name:       Applicant's full name for the letter signature (default: "Applicant")

    Returns:
        A ready-to-use, formatted cover letter — or an error message the LLM can
        communicate to the user.
    """
    logger.info(
        "generate_cover_letter tool — job='%s' at '%s', user='%s'",
        job_title, company_name, user_name,
    )
    try:
        return generate_cover_letter_core(
            resume_text=resume_text,
            job_title=job_title,
            company_name=company_name,
            job_description=job_description,
            user_name=user_name,
        )
    except ValueError as exc:
        return str(exc)
    except GeminiError as exc:
        logger.error("%s in generate_cover_letter tool: %s", type(exc).__name__, exc)
        return (
            "I encountered an issue generating the cover letter with the AI service. "
            f"Details: {exc}. Please try again in a moment."
        )
    except Exception as exc:
        logger.error("Unexpected error in generate_cover_letter tool: %s", exc, exc_info=True)
        return (
            "An unexpected error occurred while generating your cover letter. "
            "Please try again."
        )
