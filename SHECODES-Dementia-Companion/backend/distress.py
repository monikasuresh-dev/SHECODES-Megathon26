"""
Module: distress.py
Purpose: Person C - Deterministic conversational distress and confusion scoring.

Analyzes patient utterances for conversational indicators of fear, confusion,
urgency, and explicit requests for assistance.

IMPORTANT SAFETY NOTICE:
This module produces interaction and safety signals for caregiver monitoring.
It does NOT perform medical diagnosis, clinical depression assessment,
anxiety disorder evaluation, or dementia diagnosis.
"""

from typing import Any, Dict, List, Optional, Tuple
from backend.repetition import normalize_text

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================

DISTRESS_LOW_THRESHOLD: int = 30
DISTRESS_MODERATE_THRESHOLD: int = 60
DISTRESS_HIGH_THRESHOLD: int = 61

# Signal Weight Configurations
WEIGHT_MILD_WORRY: int = 18
WEIGHT_CONFUSION: int = 30
WEIGHT_LOST: int = 35
WEIGHT_FEAR: int = 35
WEIGHT_PANIC_URGENCY: int = 35
WEIGHT_HELP_REQUEST: int = 45


# ==============================================================================
# DETERMINISTIC PATTERN DICTIONARIES
# ==============================================================================

# Explicit help requests (highest priority conversational safety signals)
HELP_PATTERNS: List[Tuple[str, int, str]] = [
    ("please help me", 45, "help_request"),
    ("help me please", 45, "help_request"),
    ("can someone help me", 45, "help_request"),
    ("someone help me", 45, "help_request"),
    ("somebody help me", 45, "help_request"),
    ("somebody help", 40, "help_request"),
    ("i need help", 40, "help_request"),
    ("need help", 35, "help_request"),
    ("help me", 40, "help_request"),
    ("save me", 45, "help_request"),
    ("call someone", 35, "help_request"),
]

# Fear and acute distress patterns
FEAR_PATTERNS: List[Tuple[str, int, str]] = [
    ("i am terrified", 40, "fear"),
    ("im terrified", 40, "fear"),
    ("terrified", 35, "fear"),
    ("i am scared", 35, "fear"),
    ("im scared", 35, "fear"),
    ("i m scared", 35, "fear"),
    ("so scared", 35, "fear"),
    ("very scared", 35, "fear"),
    ("scared", 30, "fear"),
    ("i am frightened", 35, "fear"),
    ("im frightened", 35, "fear"),
    ("frightened", 30, "fear"),
    ("i am afraid", 30, "fear"),
    ("im afraid", 30, "fear"),
    ("afraid", 25, "fear"),
]

# Confusion and disorientation patterns
CONFUSION_PATTERNS: List[Tuple[str, int, str]] = [
    ("i don t know where i am", 35, "confusion"),
    ("i dont know where i am", 35, "confusion"),
    ("don t know where i am", 35, "confusion"),
    ("dont know where i am", 35, "confusion"),
    ("where am i", 30, "confusion"),
    ("what is this place", 30, "confusion"),
    ("who are you", 25, "confusion"),
    ("what is happening", 25, "confusion"),
    ("i don t understand", 25, "confusion"),
    ("i dont understand", 25, "confusion"),
    ("i am confused", 30, "confusion"),
    ("im confused", 30, "confusion"),
    ("so confused", 30, "confusion"),
    ("confused", 25, "confusion"),
]

# Lost / disorientation patterns
LOST_PATTERNS: List[Tuple[str, int, str]] = [
    ("i am lost", 35, "lost"),
    ("im lost", 35, "lost"),
    ("so lost", 35, "lost"),
    ("lost my way", 35, "lost"),
    ("can t find my way", 35, "lost"),
    ("cant find my way", 35, "lost"),
    ("where is my home", 30, "lost"),
    ("i want to go home", 30, "lost"),
    ("want to go home", 25, "lost"),
]

# Panic, acute anxiety, and urgency patterns
PANIC_PATTERNS: List[Tuple[str, int, str]] = [
    ("i am panicking", 40, "panic"),
    ("im panicking", 40, "panic"),
    ("panicking", 35, "panic"),
    ("i am in trouble", 40, "urgency"),
    ("im in trouble", 40, "urgency"),
    ("emergency", 40, "urgency"),
    ("something is wrong", 30, "urgency"),
    ("very worried", 30, "urgency"),
    ("so worried", 30, "urgency"),
    ("worried", 20, "urgency"),
]

# Mild worry patterns (to avoid false positives on routine emotional statements)
MILD_WORRY_PATTERNS: List[Tuple[str, int, str]] = [
    ("a little worried", 18, "mild_worry"),
    ("a bit worried", 18, "mild_worry"),
    ("slightly worried", 15, "mild_worry"),
    ("a little confused", 18, "mild_worry"),
    ("a bit confused", 18, "mild_worry"),
    ("a bit unsure", 15, "mild_worry"),
    ("wondering", 10, "mild_worry"),
]


class DistressScorer:
    """
    Deterministic scoring engine for patient conversational distress.
    
    Evaluates individual messages and multi-turn conversational context.
    Produces an explainable 0-100 score and classified distress level.
    """

    def __init__(
        self,
        low_threshold: int = DISTRESS_LOW_THRESHOLD,
        moderate_threshold: int = DISTRESS_MODERATE_THRESHOLD,
        high_threshold: int = DISTRESS_HIGH_THRESHOLD,
    ) -> None:
        """
        Initialize distress scorer with configurable thresholds.
        """
        self.low_threshold = low_threshold
        self.moderate_threshold = moderate_threshold
        self.high_threshold = high_threshold

    def score_single_text(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Evaluate distress signals in a single message string.
        """
        normalized = normalize_text(text)
        if not normalized:
            return {
                "distress_score": 0,
                "distress_level": "LOW",
                "signals": [],
                "signal_types": [],
            }

        detected_signals: List[Dict[str, Any]] = []
        covered_ranges: List[Tuple[int, int]] = []
        seen_types: set = set()

        # Check for mild worry first to prevent mild phrases from triggering heavy patterns
        for phrase, weight, sig_type in MILD_WORRY_PATTERNS:
            idx = normalized.find(phrase)
            if idx != -1:
                detected_signals.append({
                    "type": sig_type,
                    "weight": weight,
                    "matched_phrase": phrase,
                })
                covered_ranges.append((idx, idx + len(phrase)))
                seen_types.add(sig_type)
                break

        # Check all other categories in order of urgency
        all_pattern_groups = [
            HELP_PATTERNS,
            FEAR_PATTERNS,
            LOST_PATTERNS,
            CONFUSION_PATTERNS,
            PANIC_PATTERNS,
        ]

        for group in all_pattern_groups:
            for phrase, weight, sig_type in group:
                idx = normalized.find(phrase)
                if idx != -1:
                    overlaps = any(
                        max(idx, start) < min(idx + len(phrase), end)
                        for start, end in covered_ranges
                    )
                    if not overlaps and sig_type not in seen_types:
                        detected_signals.append({
                            "type": sig_type,
                            "weight": weight,
                            "matched_phrase": phrase,
                        })
                        covered_ranges.append((idx, idx + len(phrase)))
                        seen_types.add(sig_type)

        # Calculate composite score
        if not detected_signals:
            score = 0
        else:
            total_weight = sum(s["weight"] for s in detected_signals)
            score = min(100, total_weight)

        # Determine level
        if score >= self.high_threshold:
            level = "HIGH"
        elif score > self.low_threshold:
            level = "MODERATE"
        else:
            level = "LOW"

        signal_types = [s["type"] for s in detected_signals]

        return {
            "distress_score": score,
            "distress_level": level,
            "signals": detected_signals,
            "signal_types": signal_types,
        }

    def score_conversation(
        self,
        current_message: Optional[str],
        recent_history: Optional[List[str]] = None,
        context_window: int = 3,
    ) -> Dict[str, Any]:
        """
        Evaluate conversational distress considering current message and recent history turns.
        """
        current_result = self.score_single_text(current_message)

        if not recent_history:
            return current_result

        # Analyze recent prior turns in window
        history_window = [h for h in recent_history[-context_window:] if h]
        history_signals: List[Dict[str, Any]] = []
        seen_types = set(current_result["signal_types"])

        for past_msg in reversed(history_window):
            past_res = self.score_single_text(past_msg)
            for sig in past_res["signals"]:
                if sig["type"] not in seen_types:
                    discounted_weight = int(sig["weight"] * 0.75)
                    history_signals.append({
                        "type": sig["type"],
                        "weight": discounted_weight,
                        "matched_phrase": f"{sig['matched_phrase']} (recent history)",
                    })
                    seen_types.add(sig["type"])

        all_signals = current_result["signals"] + history_signals
        if not all_signals:
            combined_score = 0
        else:
            combined_score = min(100, sum(s["weight"] for s in all_signals))

        # Re-evaluate level
        if combined_score >= self.high_threshold:
            level = "HIGH"
        elif combined_score > self.low_threshold:
            level = "MODERATE"
        else:
            level = "LOW"

        return {
            "distress_score": combined_score,
            "distress_level": level,
            "signals": all_signals,
            "signal_types": list(seen_types),
        }
