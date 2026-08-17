"""
FinDoc Analyzer — Financial Guardrails & Validators
PII detection via presidio-analyzer (primary, already installed).
Guardrails Hub DetectPII attempted first, falls back to Presidio gracefully.
Financial-specific validators: prompt injection, SQL injection,
investment advice, hallucination indicators, numerical traceability.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


# ── Dataclasses (same pattern as previous assignment) ─────────────

@dataclass(frozen=True)
class InputDecision:
    allowed: bool
    reason:  Optional[str] = None


@dataclass(frozen=True)
class OutputDecision:
    blocked:          bool
    reason:           Optional[str]
    sanitized_text:   str
    pii_detected:     bool
    pii_summaries:    List[str]
    output_sanitized: bool


# ═══════════════════════════════════════════════════════════════════
# GuardrailsValidator — core validator class
# ═══════════════════════════════════════════════════════════════════

class GuardrailsValidator:
    """
    Financial guardrails validator.
    PII: tries Guardrails Hub DetectPII first, falls back to Presidio.
    Financial safety: prompt injection, SQL injection, investment advice,
    hallucination indicators, numerical traceability.
    """

    # ── Dangerous input patterns ──────────────────────────────────
    PROMPT_INJECTION_PATTERNS = [
        r"ignore (previous|all) instructions",
        r"you are now",
        r"forget (your|all) (previous|prior|system)",
        r"act as (a )?(different|new|another)",
        r"jailbreak",
        r"bypass (safety|guardrail|filter)",
        r"<\s*script",
        r"system\s*prompt",
        r"disregard (all|any|previous)",
        r"new personality",
    ]

    SQL_INJECTION_PATTERNS = [
        r";\s*drop\s+table",
        r";\s*delete\s+from",
        r";\s*truncate",
        r"union\s+select",
        r"1\s*=\s*1",
        r"or\s+1\s*=\s*1",
        r"--\s*$",
        r"/\*.*\*/",
        r"xp_cmdshell",
        r"exec\s*\(",
    ]

    # ── Investment advice (non-compliant) patterns ────────────────
    INVESTMENT_ADVICE_PATTERNS = [
        r"\bshould buy\b",
        r"\bshould sell\b",
        r"\bguaranteed return",
        r"\b(will|must) (go up|increase|double|skyrocket)",
        r"\binvest in\b.*\brecommend\b",
        r"\bstrong buy\b",
        r"\bsure bet\b",
        r"\brisk.free\b",
    ]

    # ── Hallucination indicators ──────────────────────────────────
    HALLUCINATION_INDICATORS = [
        r"according to my (knowledge|training|data)",
        r"as of (my|the) (last|knowledge) (update|cutoff)",
        r"i (believe|think|assume) the (revenue|profit|income)",
        r"approximately \$[\d,]+\s*(million|billion)(?!\s*(?:according|as stated|per|from|in))",
    ]

    UNCERTAINTY_PHRASES = [
        "i don't know", "i'm not sure", "i cannot", "i am unable",
        "no information", "not available", "cannot be determined",
        "insufficient data", "unclear", "uncertain",
    ]

    # ── PII entities to detect ────────────────────────────────────
    PII_ENTITIES = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD",
        "US_DRIVER_LICENSE",
        # DATE_TIME excluded — causes false positives on fiscal years (e.g. "2024")
        # PERSON/LOCATION excluded — financial reports legitimately contain executive names
    ]

    def __init__(self) -> None:
        self._pii_guard = None
        self._analyzer  = None
        self._anonymizer = None

        # Try Guardrails Hub DetectPII first
        try:
            from guardrails import Guard
            from guardrails.hub import DetectPII
            self._pii_guard = Guard().use(
                DetectPII(pii_entities=self.PII_ENTITIES, on_fail="fix")
            )
            logger.info("GuardrailsValidator: DetectPII initialized successfully")
        except Exception as e:
            logger.warning(f"DetectPII unavailable ({e}), falling back to Presidio")
            # Fall back to Presidio (already installed)
            try:
                from presidio_analyzer  import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine
                self._analyzer   = AnalyzerEngine()
                self._anonymizer = AnonymizerEngine()
                self._pii_guard  = "presidio"
                logger.info("GuardrailsValidator: Presidio PII engine initialized ✓")
            except Exception as presidio_err:
                logger.warning(f"PII protection unavailable: {presidio_err}")
                self._pii_guard = None

    # ── Input validation ──────────────────────────────────────────

    def decide_input(self, text: str) -> InputDecision:
        """Validate input query for emptiness, injection attempts."""
        if not text or not text.strip():
            return InputDecision(allowed=False, reason="Empty query")

        if len(text) > 2000:
            return InputDecision(
                allowed=False,
                reason="Query exceeds maximum length of 2000 characters"
            )

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Prompt injection blocked: pattern='{pattern}'")
                return InputDecision(
                    allowed=False,
                    reason="Query contains disallowed content (prompt injection attempt)"
                )

        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"SQL injection blocked: pattern='{pattern}'")
                return InputDecision(
                    allowed=False,
                    reason="Query contains disallowed SQL patterns"
                )

        return InputDecision(allowed=True, reason=None)

    # Alias used by FinancialGuardrailsService
    def validate_input(self, query: str) -> Tuple[bool, Optional[str]]:
        decision = self.decide_input(query)
        return decision.allowed, decision.reason

    # ── Output validation ─────────────────────────────────────────

    def validate_and_sanitize_output(self, text: str) -> OutputDecision:
        """
        Validate and sanitize LLM output.
        Runs PII detection (Guardrails Hub or Presidio),
        investment advice check, hallucination indicator check.
        """
        pii_summaries:    List[str] = []
        pii_detected:     bool      = False
        output_sanitized: bool      = False
        sanitized:        str       = text

        # ── PII detection ─────────────────────────────────────────
        if self._pii_guard is not None:
            try:
                if self._pii_guard == "presidio":
                    results = self._analyzer.analyze(
                        text=sanitized,
                        entities=self.PII_ENTITIES,
                        language="en",
                    )
                    if results:
                        anonymized = self._anonymizer.anonymize(
                            text=sanitized,
                            analyzer_results=results,
                        )
                        candidate = anonymized.text
                    else:
                        candidate = sanitized
                else:
                    result    = self._pii_guard.validate(sanitized)
                    candidate = (
                        result.validated_output
                        if getattr(result, "validated_output", None)
                        else sanitized
                    )

                if candidate != sanitized:
                    pii_detected     = True
                    output_sanitized = True
                    pii_summaries.append("PII detected and redacted")
                    sanitized = candidate

            except Exception:
                pass  # PII check failed non-fatally — continue

        # ── Investment advice detection ───────────────────────────
        for pattern in self.INVESTMENT_ADVICE_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Investment advice pattern detected: {pattern}")
                sanitized += (
                    "\n\n⚠️ Disclaimer: This analysis is for informational purposes only "
                    "and does not constitute investment advice. Consult a qualified "
                    "financial advisor before making investment decisions."
                )
                pii_summaries.append("investment_advice_disclaimer_added")
                break

        # ── Hallucination indicator detection ─────────────────────
        for pattern in self.HALLUCINATION_INDICATORS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Hallucination indicator detected: {pattern}")
                pii_summaries.append("potential_hallucination_detected")
                break

        # ── Uncertainty detection ─────────────────────────────────
        if any(phrase in sanitized.lower() for phrase in self.UNCERTAINTY_PHRASES):
            pii_summaries.append("low_confidence_response")

        return OutputDecision(
            blocked=False,
            reason=None,
            sanitized_text=sanitized,
            pii_detected=pii_detected,
            pii_summaries=pii_summaries,
            output_sanitized=output_sanitized,
        )

    # Alias used by FinancialGuardrailsService
    def validate_output(
        self,
        response: str,
        check_investment_advice: bool = True,
        check_pii: bool = True,
        check_hallucination: bool = True,
    ) -> Tuple[bool, str, List[str]]:
        decision = self.validate_and_sanitize_output(response)
        return True, decision.sanitized_text, decision.pii_summaries

    def validate_financial_claim(self, claim: str, source_context: str) -> Dict[str, Any]:
        """
        Check if numerical claims in the answer are traceable to source context.
        Numerical traceability — important for financial auditability.
        """
        numbers_in_claim = re.findall(
            r"\$?[\d,]+\.?\d*(?:\s*(?:million|billion|trillion|%|M|B|T))?",
            claim
        )
        traceable:     List[str] = []
        not_traceable: List[str] = []

        for number in numbers_in_claim:
            clean_num = re.sub(r"[,\s$]", "", number).lower()
            if len(clean_num) < 2:
                continue
            if clean_num in source_context.lower():
                traceable.append(number)
            else:
                not_traceable.append(number)

        total = len(traceable) + len(not_traceable)
        return {
            "numbers_found":     total,
            "traceable":         traceable,
            "not_traceable":     not_traceable,
            "traceability_rate": len(traceable) / total if total > 0 else 1.0,
        }


# ═══════════════════════════════════════════════════════════════════
# FinancialGuardrailsService — orchestrates full pipeline
# ═══════════════════════════════════════════════════════════════════

class FinancialGuardrailsService:
    """
    Orchestrates guardrails on every query + response.
    Called from query_routes.py for input and output validation.
    """

    def __init__(self):
        self.validator = GuardrailsValidator()

    def validate_and_annotate(
        self,
        question:       str,
        answer:         str,
        source_context: str = "",
    ) -> Dict[str, Any]:
        """
        Full guardrails pass on question + answer.
        Returns enriched result dict consumed by query_routes.py.
        """
        results: Dict[str, Any] = {
            "input_validated":            False,
            "input_error":                None,
            "output_validated":           False,
            "output_warnings":            [],
            "traceability":               None,
            "financial_disclaimer_added": False,
            "pii_redacted":               False,
        }

        # 1. Input validation
        is_valid, error = self.validator.validate_input(question)
        results["input_validated"] = is_valid
        results["input_error"]     = error
        if not is_valid:
            return results

        # 2. Output validation
        decision = self.validator.validate_and_sanitize_output(answer)
        results["output_validated"]           = True
        results["output_warnings"]            = decision.pii_summaries
        results["sanitized_answer"]           = decision.sanitized_text
        results["financial_disclaimer_added"] = any(
            "investment_advice" in w for w in decision.pii_summaries
        )
        results["pii_redacted"] = decision.pii_detected

        # 3. Numerical traceability
        if source_context:
            results["traceability"] = self.validator.validate_financial_claim(
                decision.sanitized_text, source_context
            )

        return results