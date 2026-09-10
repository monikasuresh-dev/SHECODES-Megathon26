"""
Module: intelligence.py
Purpose: Person C - Main Unified Intelligence Decision Engine.

Coordinates RepetitionTracker, DistressScorer, and EscalationManager into a
deterministic risk evaluation pipeline for elderly/dementia patient conversations.

ARCHITECTURE PRINCIPLE:
The LLM generates conversational responses.
The deterministic intelligence layer controls repetition, distress, risk, and escalation.
"""

from typing import Any, Dict, List, Optional
from backend.repetition import RepetitionTracker, normalize_text
from backend.distress import DistressScorer
from backend.escalation import EscalationManager

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================

DEFAULT_CONVERSATION_WINDOW: int = 10
DEFAULT_ESCALATE_ON_YELLOW: bool = False


class IntelligenceEngine:
    """
    Main intelligence decision engine.
    
    Provides an explainable, deterministic risk classification pipeline for
    patient conversation turns.
    """

    def __init__(
        self,
        conversation_id: str = "default",
        history_window: int = DEFAULT_CONVERSATION_WINDOW,
        escalate_on_yellow: bool = DEFAULT_ESCALATE_ON_YELLOW,
        repetition_tracker: Optional[RepetitionTracker] = None,
        distress_scorer: Optional[DistressScorer] = None,
        escalation_manager: Optional[EscalationManager] = None,
    ) -> None:
        """
        Initialize the intelligence engine.
        """
        self.conversation_id = conversation_id
        self.history_window = history_window
        self.escalate_on_yellow = escalate_on_yellow
        
        self.repetition_tracker = repetition_tracker or RepetitionTracker(
            history_window=history_window
        )
        self.distress_scorer = distress_scorer or DistressScorer()
        self.escalation_manager = escalation_manager or EscalationManager(
            escalate_on_yellow=escalate_on_yellow
        )
        
        # Internal conversation history buffer for stateful single-instance usage
        self._history: List[str] = []

    def reset(self) -> None:
        """Clear all internal conversation history and reset tracker state."""
        self._history.clear()
        self.repetition_tracker.reset()

    def _find_window_repetition(
        self,
        history: List[str],
        current_msg: str,
    ) -> Dict[str, Any]:
        """
        Inspect repetition for the current message and the recent conversation window.
        """
        current_rep = self.repetition_tracker.analyze_message(
            current_msg,
            external_history=history,
            update_internal_state=False,
        )

        if current_rep["repetition_count"] >= self.repetition_tracker.medium_threshold:
            return current_rep

        window = [h for h in history[-self.history_window:] if normalize_text(h)]
        max_rep_count = current_rep["repetition_count"]
        max_rep_level = current_rep["repetition_level"]
        max_topic = current_rep["repeated_topic"]

        for i in range(len(window)):
            test_msg = window[i]
            prior = window[:i]
            rep_check = self.repetition_tracker.analyze_message(
                test_msg,
                external_history=prior,
                update_internal_state=False,
            )
            if rep_check["repetition_count"] > max_rep_count:
                max_rep_count = rep_check["repetition_count"]
                max_rep_level = rep_check["repetition_level"]
                max_topic = rep_check["repeated_topic"]

        return {
            "repetition_count": max_rep_count,
            "repetition_level": max_rep_level,
            "repeated_topic": max_topic,
            "is_repeating": max_rep_count >= self.repetition_tracker.medium_threshold,
            "current_message_rep": current_rep,
        }

    def process_message(
        self,
        patient_message: Optional[str],
        conversation_history: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Public integration interface for Person B and Person D.
        
        Args:
            patient_message: The current patient text input (handles None, empty string safely).
            conversation_history: Optional external list of prior patient message strings.
                                  If None, the engine uses its internal history.
                                  
        Returns:
            Structured dictionary matching the required Person B / Person A contract:
            {
                "risk_level": "GREEN" | "YELLOW" | "RED",
                "distress_score": int (0-100),
                "distress_level": "LOW" | "MODERATE" | "HIGH",
                "repetition_count": int,
                "repetition_level": "LOW" | "MEDIUM" | "HIGH",
                "escalate": bool,
                "reason": str,
                "signals": List[str]
            }
        """
        if conversation_history is not None:
            effective_history = list(conversation_history)
        else:
            effective_history = list(self._history)

        normalized_msg = normalize_text(patient_message)

        if not normalized_msg:
            return {
                "risk_level": "GREEN",
                "distress_score": 0,
                "distress_level": "LOW",
                "repetition_count": 0,
                "repetition_level": "LOW",
                "escalate": False,
                "reason": "Normal conversation with low distress",
                "signals": [],
            }

        # 1. Evaluate distress on current message and recent history context
        distress_eval = self.distress_scorer.score_conversation(
            current_message=patient_message,
            recent_history=effective_history,
            context_window=3,
        )

        # 2. Evaluate repetition
        current_msg_eval = self.repetition_tracker.analyze_message(
            message=patient_message,
            external_history=effective_history,
            update_internal_state=False,
        )

        # If distress is present, check window repetition too
        if distress_eval["distress_score"] > self.distress_scorer.low_threshold:
            rep_eval = self._find_window_repetition(effective_history, patient_message)
        else:
            rep_eval = current_msg_eval

        # 3. Classify Risk & Escalation via EscalationManager
        classification = self.escalation_manager.classify_interaction(
            distress_score=distress_eval["distress_score"],
            distress_level=distress_eval["distress_level"],
            distress_signals=distress_eval["signals"],
            repetition_count=rep_eval["repetition_count"],
            repetition_level=rep_eval["repetition_level"],
            repeated_topic=rep_eval["repeated_topic"],
            patient_message=patient_message,
        )

        # Update internal history if external history was not provided
        if conversation_history is None:
            self._history.append(patient_message)
            if len(self._history) > self.history_window * 2:
                self._history = self._history[-self.history_window:]
            self.repetition_tracker.analyze_message(
                message=patient_message,
                update_internal_state=True,
            )

        return {
            "risk_level": classification["risk_level"],
            "distress_score": distress_eval["distress_score"],
            "distress_level": distress_eval["distress_level"],
            "repetition_count": rep_eval["repetition_count"],
            "repetition_level": rep_eval["repetition_level"],
            "escalate": classification["escalate"],
            "reason": classification["reason"],
            "signals": classification["signals"],
            "repeated_topic": rep_eval.get("repeated_topic"),
        }
