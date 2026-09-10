"""
Module: call_session.py
Purpose: In-memory Call Session Manager for WebRTC human-to-human audio live sessions.
Supports signaling: session creation, caregiver join, offer, answer, ICE candidate exchange,
and session termination with thread-safety and TTL expiration.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid


class CallSession:
    """
    Represents a single WebRTC audio call session between a patient and a caregiver.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        patient_id: str = "PATIENT-84920",
        alert_id: Optional[str] = None,
    ) -> None:
        self.session_id: str = session_id or f"call_{uuid.uuid4().hex[:8]}"
        self.patient_id: str = patient_id
        self.alert_id: Optional[str] = alert_id
        self.status: str = "WAITING"  # WAITING, CONNECTING, CONNECTED, ENDED, FAILED, EXPIRED
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at
        self.caregiver_joined: bool = False
        self.patient_joined: bool = False
        self.offer: Optional[Dict[str, Any]] = None
        self.answer: Optional[Dict[str, Any]] = None
        self.caregiver_ice_candidates: List[Dict[str, Any]] = []
        self.patient_ice_candidates: List[Dict[str, Any]] = []
        self.ended_by: Optional[str] = None

    def touch(self) -> None:
        """Update last modified timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def is_active(self) -> bool:
        """Check if call session is still active/connectable."""
        return self.status in ("WAITING", "CONNECTING", "CONNECTED")

    def is_expired(self, ttl_seconds: int = 1800) -> bool:
        """Check if session exceeded TTL since last update."""
        try:
            updated_dt = datetime.fromisoformat(self.updated_at)
            now_dt = datetime.now(timezone.utc)
            delta = (now_dt - updated_dt).total_seconds()
            return delta > ttl_seconds
        except Exception:
            return False

    def end(self, ended_by: str = "system") -> None:
        """Mark session as ended."""
        self.status = "ENDED"
        self.ended_by = ended_by
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state for API clients."""
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "alert_id": self.alert_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "caregiver_joined": self.caregiver_joined,
            "patient_joined": self.patient_joined,
            "has_offer": self.offer is not None,
            "has_answer": self.answer is not None,
            "offer": self.offer,
            "answer": self.answer,
            "caregiver_ice_candidates": list(self.caregiver_ice_candidates),
            "patient_ice_candidates": list(self.patient_ice_candidates),
            "ended_by": self.ended_by,
        }


class CallSessionManager:
    """
    Thread-safe manager for active call sessions.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, CallSession] = {}

    def create_session(
        self,
        patient_id: str = "PATIENT-84920",
        session_id: Optional[str] = None,
        alert_id: Optional[str] = None,
    ) -> CallSession:
        """
        Create a new call session, or reset an existing session if session_id provided.
        """
        with self._lock:
            # End any existing active session for this patient to prevent orphan calls
            for existing in self._sessions.values():
                if existing.patient_id == patient_id and existing.is_active():
                    existing.end(ended_by="new_session_override")

            session = CallSession(session_id=session_id, patient_id=patient_id, alert_id=alert_id)
            self._sessions[session.session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[CallSession]:
        """Retrieve session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_active_session(self, patient_id: Optional[str] = None) -> Optional[CallSession]:
        """Find the latest active/waiting session."""
        with self._lock:
            active_sessions = [
                s for s in self._sessions.values()
                if s.is_active() and (patient_id is None or s.patient_id == patient_id)
            ]
            if not active_sessions:
                return None
            # Return most recently updated active session
            active_sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return active_sessions[0]

    def join_session(self, session_id: str, role: str = "caregiver") -> Tuple[bool, Optional[str], Optional[CallSession]]:
        """
        Join a call session as caregiver or patient.
        Returns: (success, error_message, session)
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found", None

            if not session.is_active():
                return False, f"Cannot join session in status '{session.status}'", session

            if role == "caregiver":
                if session.caregiver_joined:
                    return False, "Caregiver already joined this session", session
                session.caregiver_joined = True
            elif role == "patient":
                if session.patient_joined:
                    return False, "Patient already joined this session", session
                session.patient_joined = True
            else:
                return False, f"Invalid role '{role}'", session

            session.touch()
            return True, None, session

    def set_offer(
        self,
        session_id: str,
        offer: Dict[str, Any],
        role: str = "caregiver",
    ) -> Tuple[bool, Optional[str], Optional[CallSession]]:
        """
        Set WebRTC SDP offer.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found", None

            if not session.is_active():
                return False, f"Cannot set offer on session with status '{session.status}'", session

            if not isinstance(offer, dict) or "sdp" not in offer or "type" not in offer:
                return False, "Malformed offer payload: must contain 'type' and 'sdp'", session

            if session.offer is not None:
                return False, "Offer already submitted for this session", session

            session.offer = offer
            if session.status == "WAITING":
                session.status = "CONNECTING"
            session.touch()
            return True, None, session

    def set_answer(
        self,
        session_id: str,
        answer: Dict[str, Any],
        role: str = "patient",
    ) -> Tuple[bool, Optional[str], Optional[CallSession]]:
        """
        Set WebRTC SDP answer.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found", None

            if not session.is_active():
                return False, f"Cannot set answer on session with status '{session.status}'", session

            if not isinstance(answer, dict) or "sdp" not in answer or "type" not in answer:
                return False, "Malformed answer payload: must contain 'type' and 'sdp'", session

            if session.offer is None:
                return False, "Cannot set answer before offer is received", session

            if session.answer is not None:
                return False, "Answer already submitted for this session", session

            session.answer = answer
            session.status = "CONNECTED"
            session.touch()
            return True, None, session

    def add_ice_candidate(
        self,
        session_id: str,
        candidate: Dict[str, Any],
        role: str,
    ) -> Tuple[bool, Optional[str], int]:
        """
        Add an ICE candidate for patient or caregiver.
        Returns: (success, error_message, candidate_count)
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found", 0

            if not session.is_active():
                return False, f"Cannot add ICE candidates to session with status '{session.status}'", 0

            if not isinstance(candidate, dict):
                return False, "Malformed candidate payload: must be a dictionary", 0

            if role == "caregiver":
                session.caregiver_ice_candidates.append(candidate)
                count = len(session.caregiver_ice_candidates)
            elif role == "patient":
                session.patient_ice_candidates.append(candidate)
                count = len(session.patient_ice_candidates)
            else:
                return False, f"Invalid role '{role}' for ICE candidate", 0

            session.touch()
            return True, None, count

    def end_session(self, session_id: str, ended_by: str = "user") -> Tuple[bool, Optional[str], Optional[CallSession]]:
        """
        End an active call session.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found", None

            session.end(ended_by=ended_by)
            return True, None, session

    def cleanup_expired_sessions(self, ttl_seconds: int = 1800) -> int:
        """
        Remove expired sessions to prevent memory leaks.
        """
        with self._lock:
            expired_ids = [
                s_id for s_id, s in self._sessions.items()
                if s.is_expired(ttl_seconds) or (s.status in ("ENDED", "FAILED") and s.is_expired(300))
            ]
            for s_id in expired_ids:
                del self._sessions[s_id]
            return len(expired_ids)


# Global singleton manager
call_session_manager = CallSessionManager()
