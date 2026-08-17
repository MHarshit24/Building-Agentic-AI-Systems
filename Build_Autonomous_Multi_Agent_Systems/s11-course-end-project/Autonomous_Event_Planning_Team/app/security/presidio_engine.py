"""Responsible for Presidio-based privacy protection integration.

Best-effort and config-gated: if `presidio_enabled` is False, or the
`presidio_analyzer`/`presidio_anonymizer` packages fail to initialize (e.g.
the spaCy model they depend on isn't installed), scrubbing silently no-ops
rather than blocking a planning request.
"""

from functools import lru_cache

from app.config import get_settings


@lru_cache
def _get_engines():
    if not get_settings().presidio_enabled:
        return None
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        return AnalyzerEngine(), AnonymizerEngine()
    except BaseException:
        # Must catch BaseException, not just Exception: a missing spaCy
        # model makes presidio_analyzer call spacy.cli.download(), which
        # raises SystemExit (a BaseException, not an Exception) on failure
        # (e.g. no write permission to install it) - left uncaught, that
        # crashes the whole ASGI app instead of no-opping as documented.
        return None


def scrub(text: str) -> str:
    """Replace detected PII entities in text with anonymized placeholders.
    Returns text unchanged if Presidio is disabled or unavailable."""
    if not text:
        return text

    engines = _get_engines()
    if engines is None:
        return text

    analyzer, anonymizer = engines
    try:
        results = analyzer.analyze(text=text, language="en")
        if not results:
            return text
        return anonymizer.anonymize(text=text, analyzer_results=results).text
    except Exception:
        return text
