"""
Module: escalation.py
Purpose: Risk classification, escalation decision engine, and caregiver alert manager.

Translates repetition and distress signals into GREEN, YELLOW, or RED risk levels,
manages escalation thresholds, and formats real-time alerts for the caregiver dashboard.

SAFETY PRINCIPLE:
Escalation indicates conversational monitoring or caregiver notification.
It does NOT perform medical diagnosis or call 911 emergency services.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================

DEFAULT_ESCALATE_ON_YELLOW: bool = False
MAX_STORED_ALERTS: int = 50
MAX_STORED_EVENTS: int = 100


class EscalationManager:
    """
    Evaluates risk classification, escalation triggers, and caregiver notifications.
    Thread-safe storage for active alerts and interaction history.
    """

    def __init__(self, escalate_on_yellow: bool = DEFAULT_ESCALATE_ON_YELLOW) -> None:
        self.escalate_on_yellow = escalate_on_yellow
        self._lock = threading.Lock()
        self._alerts: List[Dict[str, Any]] = []
        self._recent_events: List[Dict[str, Any]] = []

    def classify_interaction(
        self,
        distress_score: int,
        distress_level: str,
        distress_signals: List[Dict[str, Any]],
        repetition_count: int,
        repetition_level: str,
        repeated_topic: Optional[str] = None,
        patient_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classifies interaction into GREEN, YELLOW, or RED with explainable reason.
        
        Returns:
            Dict containing:
            - risk_level: "GREEN" | "YELLOW" | "RED"
            - escalate: bool
            - reason: str
            - signals: List[str]
            - recommended_action: str
        """
        signal_types = [s.get("type", "") for s in distress_signals]
        has_help_request = "help_request" in signal_types
        has_fear = "fear" in signal_types
        has_confusion = "confusion" in signal_types or "lost" in signal_types

        has_physical_distress = "physical_distress" in signal_types

        # List of high-level signals for judges, caregiver UI, and Person A
        active_signals: List[str] = []

        if repetition_level in ("MEDIUM", "HIGH"):
            active_signals.append("repeated_question")

        if distress_level == "HIGH":
            active_signals.append("high_distress")
        elif distress_level == "MODERATE":
            active_signals.append("moderate_distress")

        for sig in ("fear", "confusion", "help_request", "lost", "panic", "urgency", "mild_worry", "physical_distress"):
            if sig in signal_types and sig not in active_signals:
                active_signals.append(sig)

        # ----------------------------------------------------------------------
        # 1. RED CLASSIFICATION (Caregiver Attention Required)
        # ----------------------------------------------------------------------
        is_red = False
        reason = ""
        action = "No action needed. Normal conversational state."

        if has_physical_distress:
            is_red = True
            reason = "Physical distress or dizziness reported - caregiver check-in required"
            action = "Connect live call with primary caregiver and verify physical stability."

        elif repetition_count >= 5 or (repetition_count >= 4 and repeated_topic == "daughter"):
            is_red = True
            reason = f"Severe perseverative repetition regarding '{repeated_topic or 'concern'}' - caregiver check-in recommended"
            action = "Connect call with primary caregiver and provide reassuring presence."

        elif distress_level == "HIGH":
            is_red = True
            if has_help_request and (has_fear or has_confusion):
                reason = "High conversational distress with a strong help request"
            elif repetition_level in ("MEDIUM", "HIGH"):
                reason = "High distress combined with repeated concern"
            elif has_help_request:
                reason = "High conversational distress with a direct request for help"
            else:
                reason = "High conversational distress detected"
            action = "Check in on patient room or call familiar contact."

        elif has_help_request and distress_score >= 40:
            is_red = True
            if repetition_level in ("MEDIUM", "HIGH"):
                reason = "Direct request for help with repeated concern"
            else:
                reason = "High conversational distress with a strong help request"
            action = "Caregiver check-in recommended."

        elif distress_level == "MODERATE" and repetition_level == "HIGH":
            is_red = True
            reason = "High repetition of concern combined with moderate distress"
            action = "Provide gentle grounding and verify patient comfort."

        if is_red:
            return {
                "risk_level": "RED",
                "escalate": True,
                "reason": reason,
                "signals": active_signals,
                "recommended_action": action,
            }

        # ----------------------------------------------------------------------
        # 2. YELLOW CLASSIFICATION (Active Monitoring)
        # ----------------------------------------------------------------------
        is_yellow = False

        if repetition_level in ("MEDIUM", "HIGH") and distress_level == "MODERATE":
            is_yellow = True
            topic_str = f" regarding '{repeated_topic}'" if repeated_topic else ""
            reason = f"Repeated concern{topic_str} with moderate distress"
            action = "Monitor conversation; companion will use grounding cues."

        elif repetition_level in ("MEDIUM", "HIGH"):
            is_yellow = True
            topic_str = f" regarding '{repeated_topic}'" if repeated_topic else ""
            reason = f"Repeated concern detected{topic_str}"
            action = "Continue reassuring routine; monitor for distress buildup."

        elif distress_level == "MODERATE":
            is_yellow = True
            if has_confusion:
                reason = "Conversational confusion or disorientation detected"
            else:
                reason = "Moderate conversational distress detected"
            action = "Companion offering grounding reassurance."

        if is_yellow:
            return {
                "risk_level": "YELLOW",
                "escalate": self.escalate_on_yellow,
                "reason": reason,
                "signals": active_signals,
                "recommended_action": action,
            }

        # ----------------------------------------------------------------------
        # 3. GREEN CLASSIFICATION (Normal)
        # ----------------------------------------------------------------------
        return {
            "risk_level": "GREEN",
            "escalate": False,
            "reason": "Normal conversation with low distress",
            "signals": active_signals,
            "recommended_action": "Standard companion interaction.",
        }

    def record_interaction(
        self,
        patient_message: str,
        reply: str,
        intelligence_result: Dict[str, Any],
        patient_id: str = "PATIENT-84920",
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record event for caregiver timeline and generate alert if escalated.
        """
        now = datetime.now(timezone.utc).isoformat()
        risk_level = intelligence_result.get("risk_level", "GREEN")
        escalate = intelligence_result.get("escalate", False)

        event_record = {
            "timestamp": now,
            "patient_message": patient_message,
            "companion_reply": reply,
            "risk_level": risk_level,
            "distress_score": intelligence_result.get("distress_score", 0),
            "repetition_count": intelligence_result.get("repetition_count", 0),
            "reason": intelligence_result.get("reason", ""),
            "signals": intelligence_result.get("signals", []),
        }

        with self._lock:
            self._recent_events.append(event_record)
            if len(self._recent_events) > MAX_STORED_EVENTS:
                self._recent_events.pop(0)

            alert_record = None
            if escalate or risk_level == "RED":
                alert_record = {
                    "alert_id": f"ALT-{int(datetime.now(timezone.utc).timestamp())}",
                    "timestamp": now,
                    "patient_id": patient_id,
                    "session_id": session_id,
                    "risk_level": risk_level,
                    "distress_score": intelligence_result.get("distress_score", 0),
                    "repetition_count": intelligence_result.get("repetition_count", 0),
                    "reason": intelligence_result.get("reason", ""),
                    "signals": intelligence_result.get("signals", []),
                    "status": "ACTIVE",
                    "recommended_action": intelligence_result.get("recommended_action", "Caregiver check-in recommended."),
                }
                self._alerts.append(alert_record)
                if len(self._alerts) > MAX_STORED_ALERTS:
                    self._alerts.pop(0)

            return alert_record

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get summarized data for caregiver dashboard."""
        with self._lock:
            latest_event = self._recent_events[-1] if self._recent_events else None
            current_risk = latest_event["risk_level"] if latest_event else "GREEN"
            current_score = latest_event["distress_score"] if latest_event else 0
            
            active_alerts = [a for a in self._alerts if a.get("status") == "ACTIVE"]

            return {
                "current_risk_level": current_risk,
                "current_distress_score": current_score,
                "active_alerts_count": len(active_alerts),
                "active_alerts": list(reversed(active_alerts)),
                "recent_events": list(reversed(self._recent_events[-15:])),
            }

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged by caregiver."""
        with self._lock:
            for alert in self._alerts:
                if alert["alert_id"] == alert_id:
                    alert["status"] = "ACKNOWLEDGED"
                    return True
            return False
