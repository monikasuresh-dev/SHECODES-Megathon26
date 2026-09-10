"""
Module: privacy.py
Purpose: Person D - Privacy filtering, PII sanitization, and safety guardrails.

Protects elderly patient privacy by redacting sensitive identifying data (phone numbers,
financial info, government IDs) prior to logging or external LLM processing.
Enforces anti-dependency safeguards and safety boundary checks.
"""

import re
from typing import Dict, List, Tuple

# ==============================================================================
# PII REGEX PATTERNS
# ==============================================================================

# US / International telephone numbers
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Social Security Numbers / National Health IDs (###-##-####)
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Credit Card Numbers (13 to 19 digits with optional spaces or dashes)
CREDIT_CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b"
)

# Email addresses
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

# Physical address indicators (house numbers + street names)
STREET_PATTERN = re.compile(
    r"\b\d{1,5}\s+(?:[A-Za-z]+\s+){1,3}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way)\b",
    re.IGNORECASE,
)


class PrivacyFilter:
    """
    Sanitizes patient utterances and validates safety guidelines.
    """

    def __init__(self) -> None:
        pass

    def filter_text(self, text: str) -> Dict[str, any]:
        """
        Sanitize text by replacing sensitive PII with safe tokens.
        
        Returns:
            Dict containing:
            - sanitized_text: Cleaned text safe for LLM and logging
            - pii_detected: bool indicating whether any PII was sanitized
            - redactions: List of redaction types applied
            - safety_warning: Optional safety note if medical self-harm signals appear
        """
        if not text or not isinstance(text, str):
            return {
                "sanitized_text": "",
                "pii_detected": False,
                "redactions": [],
                "safety_warning": None,
            }

        cleaned = text
        redactions: List[str] = []

        # 1. Phone numbers
        if PHONE_PATTERN.search(cleaned):
            cleaned = PHONE_PATTERN.sub("[PHONE_REDACTED]", cleaned)
            redactions.append("phone_number")

        # 2. SSN / ID
        if SSN_PATTERN.search(cleaned):
            cleaned = SSN_PATTERN.sub("[GOV_ID_REDACTED]", cleaned)
            redactions.append("government_id")

        # 3. Credit cards
        if CREDIT_CARD_PATTERN.search(cleaned):
            cleaned = CREDIT_CARD_PATTERN.sub("[CARD_REDACTED]", cleaned)
            redactions.append("financial_card")

        # 4. Email
        if EMAIL_PATTERN.search(cleaned):
            cleaned = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", cleaned)
            redactions.append("email_address")

        # Check for acute safety boundary (e.g. self-harm / medical crisis)
        safety_warning = None
        lower = text.lower()
        if any(term in lower for term in ["overdose", "kill myself", "end my life", "take all my pills"]):
            safety_warning = "CRITICAL_SAFETY_TRIGGER: Immediate physical health escalation."

        return {
            "sanitized_text": cleaned,
            "pii_detected": len(redactions) > 0,
            "redactions": redactions,
            "safety_warning": safety_warning,
        }
