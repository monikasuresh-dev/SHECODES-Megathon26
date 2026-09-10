"""
Module: static_responses.py
Purpose: Person B - Deterministic, patient-grounded offline response generator.

Provides reassuring, dementia-appropriate responses grounded in patient.json memory anchors
when the external LLM API is offline, disabled, or rate-limited.

DEMENTIA CARE PRINCIPLES:
- Validation Therapy: never argue, dispute, or abruptly correct dates/memories.
- Grounding Anchors: mention familiar anchors (Ananya's 5:30 PM visit, Muthu, and the Anna Nagar home).
- Short & Gentle: 1 to 2 calming sentences.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def get_time_greeting() -> str:
    """Determine time-aware greeting (good morning / good afternoon / good evening / good night)."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "good morning"
    elif 12 <= hour < 17:
        return "good afternoon"
    elif 17 <= hour < 21:
        return "good evening"
    else:
        return "good night"


class StaticResponseGenerator:
    """
    Generates comforting, context-aware responses without requiring external LLM network calls.
    """

    def __init__(self, patient_profile: Optional[Dict[str, Any]] = None) -> None:
        self.patient_profile = patient_profile or {}

    def update_profile(self, patient_profile: Dict[str, Any]) -> None:
        self.patient_profile = patient_profile

    def generate_response(
        self,
        sanitized_message: str,
        intelligence_result: Dict[str, Any],
    ) -> str:
        """
        Generate a patient-specific comforting response based on message content,
        patient memory anchors, and intelligence signals.
        """
        lower = sanitized_message.lower()
        signals = intelligence_result.get("signals", [])
        risk_level = intelligence_result.get("risk_level", "GREEN")
        repeated_topic = intelligence_result.get("repeated_topic", "")

        # Extract patient anchors
        preferred_name = self.patient_profile.get("preferred_name", "Lakshmi")
        daughter_info = (
            self.patient_profile.get("family_and_contacts", {})
            .get("primary_caregiver", {})
        )
        daughter_name = daughter_info.get("name", "Ananya Narayanan").split()[0]
        visit_schedule = daughter_info.get("visit_schedule", "this evening around 5:30 PM")
        
        comfort_anchors = self.patient_profile.get("comfort_anchors", {})
        pet_name = comfort_anchors.get("cherished_pet", {}).get("name", "Muthu")
        room_number = self.patient_profile.get("room_number", "Anna Nagar, Chennai")

        # ----------------------------------------------------------------------
        # 1. PHYSICAL DISTRESS & DIZZINESS (RED ESCALATION REDIRECT)
        # ----------------------------------------------------------------------
        if "physical_distress" in signals or any(w in lower for w in ["dizzy", "dizziness", "not feeling well", "feel sick", "faint", "fell down", "spinning"]):
            return (
                f"Please sit down and rest comfortably, {preferred_name}. You are safe. "
                f"I am alerting {daughter_name} right away to check in on you."
            )

        # ----------------------------------------------------------------------
        # 1b. SEVERE REPETITION OR RISKY RED SITUATION (CONNECT CAREGIVER)
        # ----------------------------------------------------------------------
        if risk_level == "RED" and (repeated_topic == "daughter" or "daughter" in lower):
            return (
                f"{daughter_name} loves you dearly, {preferred_name}. "
                f"I am connecting you with {daughter_name} right now. You are safe."
            )

        # ----------------------------------------------------------------------
        # 1c. ACUTE HELP / DISTRESS SIGNALS (RED / HIGH DISTRESS)
        # ----------------------------------------------------------------------
        if "help_request" in signals or "help" in lower:
            return (
                f"I am right here with you, {preferred_name}. "
                f"You are completely safe, and I have notified {daughter_name} and our staff to check in on you."
            )

        if "fear" in signals or any(w in lower for w in ["scared", "terrified", "frightened"]):
            return (
                f"It is completely okay to feel a little worried, {preferred_name}. "
                f"You are safe here in {room_number}. Let's take a slow, gentle breath together."
            )

        # ----------------------------------------------------------------------
        # 2. CONFUSION & DISORIENTATION SIGNALS
        # ----------------------------------------------------------------------
        if "confusion" in signals or "lost" in signals or any(w in lower for w in ["where am i", "lost", "home"]):
            return (
                f"You are right in your cozy room at {room_number}, sitting in your favorite armchair. "
                f"Everything is peaceful, and {daughter_name} will be visiting you {visit_schedule}."
            )

        # ----------------------------------------------------------------------
        # 3. REPEATED DAUGHTER / FAMILY INQUIRIES
        # ----------------------------------------------------------------------
        if repeated_topic == "daughter" or any(w in lower for w in ["daughter", "sarah"]):
            return (
                f"{daughter_name} loves you dearly, {preferred_name}. "
                f"She will be here to see you {visit_schedule}. {pet_name} is doing wonderfully too."
            )

        if "son" in lower or "ravi" in lower:
            return (
                f"Ravi called from Bengaluru to send you all his love, {preferred_name}. "
                f"He is looking forward to chatting on Sunday morning."
            )

        # ----------------------------------------------------------------------
        # 4. ROUTINE & COMFORT ANCHORS (TEA, GARDEN, WEATHER, MUSIC)
        # ----------------------------------------------------------------------
        if any(w in lower for w in ["tea", "breakfast", "lunch", "dinner", "eat", "hungry"]):
            return (
                f"Your warm tea and a light snack will be ready shortly, {preferred_name}. "
                f"Your familiar home routine is going well."
            )

        if any(w in lower for w in ["weather", "sun", "rain", "outside", "garden"]):
            return (
                f"It is a lovely day outside, {preferred_name}. "
                f"The plants near the veranda are looking lovely today."
            )

        if any(w in lower for w in ["barnaby", "dog", "pet"]):
            return (
                f"{pet_name} is having a happy day playing in the garden at {daughter_name}'s house. "
                f"He wags his tail whenever we mention your name."
            )

        if any(w in lower for w in ["music", "piano", "song", "carnatic", "tamil"]):
            return (
                f"Listening to familiar Carnatic music and Tamil songs always brings so much calm. "
                f"Would you like to relax and listen for a while?"
            )

        # ----------------------------------------------------------------------
        # 5. GREETINGS (TIME-AWARE GREETING WITH PATIENT NAME)
        # ----------------------------------------------------------------------
        if any(w in lower for w in ["hey", "hello", "hi", "good morning", "good afternoon", "good evening", "good night"]):
            time_greet = get_time_greeting()
            return f"Hey {preferred_name}, {time_greet}! How are you?"

        if any(w in lower for w in ["thank you", "thanks"]):
            return (
                f"You are always so kind, {preferred_name}. I am always here whenever you want to talk."
            )

        # ----------------------------------------------------------------------
        # 6. NORMAL SITUATION REASSURANCE
        # ----------------------------------------------------------------------
        return "Okay, you are good, well and fine, you are warm and safe."
