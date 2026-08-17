"""
Job Search Tool — powered by SerpAPI Google Jobs
-------------------------------------------------
Public API
~~~~~~~~~~
``fetch_job_listings(query, location)``
    Core function — raises ``SerpApiError`` subclasses on failure.
    Used by the direct REST endpoint ``POST /api/jobs/search``.

``search_jobs`` (LangChain @tool)
    Thin wrapper — returns a human-readable error string on failure so the
    LLM agent can respond gracefully instead of crashing.
    Used only by the AgentExecutor inside the chat flow.
"""
import os
import logging
from typing import Optional

from langchain.tools import tool

from exceptions import (
    SerpApiConfigError,
    SerpApiError,
    SerpApiNetworkError,
    SerpApiRateLimitError,
)

logger = logging.getLogger(__name__)


# ── SerpAPI client ────────────────────────────────────────────────────────────

def _call_serpapi(query: str, location: str) -> list[dict]:
    """
    Call the SerpAPI Google Jobs engine and return raw job result dicts.

    Raises:
        SerpApiConfigError:    SERPAPI_API_KEY missing or invalid.
        SerpApiRateLimitError: API quota or rate limit exceeded.
        SerpApiNetworkError:   SerpAPI unreachable.
        SerpApiError:          Any other SerpAPI error.
    """
    try:
        from serpapi import GoogleSearch
    except ImportError as exc:
        raise SerpApiConfigError(
            "SerpAPI client not installed. Run: pip install google-search-results"
        ) from exc

    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise SerpApiConfigError(
            "SERPAPI_API_KEY environment variable is not set. "
            "Add it to your .env file or deployment secrets."
        )

    search_query = f"{query} {location}".strip() if location else query
    params = {
        "engine":  "google_jobs",
        "q":       search_query,
        "api_key": api_key,
        "hl":      "en",
        "gl":      "us",
        "num":     10,
    }
    if location:
        params["location"] = location

    try:
        search  = GoogleSearch(params)
        results = search.get_dict()
    except Exception as exc:
        msg = str(exc).lower()
        if "connection" in msg or "timeout" in msg:
            raise SerpApiNetworkError(
                f"Could not reach SerpAPI: {exc}"
            ) from exc
        raise SerpApiError(f"SerpAPI request failed: {exc}") from exc

    # SerpAPI embeds errors inside the response dict
    if "error" in results:
        error_msg = results["error"]
        err_lower = error_msg.lower()
        if "rate limit" in err_lower or "quota" in err_lower or "429" in err_lower:
            raise SerpApiRateLimitError(
                f"SerpAPI rate limit / quota exceeded: {error_msg}"
            )
        if "api key" in err_lower or "invalid key" in err_lower or "authentication" in err_lower:
            raise SerpApiConfigError(
                f"SerpAPI authentication error: {error_msg}"
            )
        raise SerpApiError(f"SerpAPI returned an error: {error_msg}")

    return results.get("jobs_results", [])


# ── Formatter ─────────────────────────────────────────────────────────────────

def _format_job_listings(jobs: list[dict]) -> str:
    """Format raw SerpAPI job dicts into a user-friendly markdown string."""
    if not jobs:
        return (
            "No job listings found for your search. "
            "Try broadening the role title or using a different city."
        )

    lines = [f"Here are **{len(jobs)} job listings** I found:\n"]

    for i, job in enumerate(jobs, 1):
        title       = job.get("title", "N/A")
        company     = job.get("company_name", "N/A")
        location    = job.get("location", "N/A")
        via         = job.get("via", "")
        description = job.get("description", "")
        highlights  = job.get("job_highlights", [])

        short_desc = (description[:220] + "…") if len(description) > 220 else description

        qualifications: list[str] = []
        for section in highlights:
            if section.get("title", "").lower() in ("qualifications", "responsibilities"):
                qualifications = section.get("items", [])[:4]
                break

        related_links = job.get("related_links", [])
        apply_link    = related_links[0].get("link", "") if related_links else ""

        lines.append(f"---\n**{i}. {title}**")
        lines.append(f"   Company: {company}")
        lines.append(f"   Location: {location}")
        if via:
            lines.append(f"   Via: {via}")
        if short_desc:
            lines.append(f"   Summary: {short_desc}")
        if qualifications:
            lines.append("   Key Requirements:")
            for req in qualifications:
                lines.append(f"      - {req}")
        if apply_link:
            lines.append(f"   Apply: {apply_link}")
        lines.append("")

    lines.append(
        "_Would you like me to analyze your resume against these roles, "
        "or generate a cover letter for any of these positions?_"
    )
    return "\n".join(lines)


# ── Public core function (used by direct REST endpoints) ──────────────────────

def fetch_job_listings(query: str, location: str = "") -> str:
    """
    Search for job listings and return a formatted markdown string.

    This is the **core function** consumed by the direct REST endpoint
    ``POST /api/jobs/search``. It raises domain exceptions on failure so
    the global error handler can return the correct HTTP status code.

    Args:
        query:    Job title or role keyword (e.g. "Python Engineer").
        location: City, state, or country (optional).

    Returns:
        Formatted markdown string with job listings.

    Raises:
        SerpApiConfigError:    Missing or invalid API key.
        SerpApiRateLimitError: Rate limit or quota exceeded.
        SerpApiNetworkError:   SerpAPI unreachable.
        SerpApiError:          Any other SerpAPI failure.
    """
    logger.info("fetch_job_listings — query='%s', location='%s'", query, location)
    jobs = _call_serpapi(query, location)
    return _format_job_listings(jobs)


# ── LangChain tool (used by the AgentExecutor inside the chat flow) ───────────

@tool
def search_jobs(query: str, location: str = "") -> str:
    """
    Search for live job listings using Google Jobs (via SerpAPI).

    Use this tool when the user wants to find job opportunities.
    Requires a job title or role; location is optional but recommended.

    Args:
        query:    Job title, role, or keyword (e.g. "Software Engineer")
        location: City, state, or country (e.g. "New York", "Remote", "London")

    Returns:
        Formatted list of up to 10 job listings with title, company, location,
        and apply link — or an error message the LLM can communicate to the user.
    """
    logger.info("search_jobs tool — query='%s', location='%s'", query, location)
    try:
        return fetch_job_listings(query, location)
    except SerpApiConfigError as exc:
        logger.error("SerpApiConfigError: %s", exc)
        return (
            "I'm unable to search for jobs right now due to a configuration issue. "
            "Please contact the administrator to verify the SERPAPI_API_KEY."
        )
    except SerpApiRateLimitError as exc:
        logger.warning("SerpApiRateLimitError: %s", exc)
        return (
            "The job search service has hit its rate limit. "
            "Please try again in a few minutes, or search directly on LinkedIn or Indeed."
        )
    except SerpApiNetworkError as exc:
        logger.warning("SerpApiNetworkError: %s", exc)
        return (
            "I couldn't reach the job search service right now. "
            "Please check your connection and try again shortly."
        )
    except SerpApiError as exc:
        logger.error("SerpApiError: %s", exc, exc_info=True)
        return (
            f"The job search encountered an error: {exc}. "
            "Please try again or search on LinkedIn/Indeed directly."
        )
