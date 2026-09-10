"""
Module: prompt.py
Purpose: Person B - Dementia-tailored Prompt Builder for LLM integration.

Constructs grounded system instructions and dynamic conversational prompts
using persistent patient memory (patient.json) and Person C intelligence signals.

CARE PRINCIPLES:
- Compassionate validation therapy (never dispute memories or argue).
- Grounding anchors (family visits, cherished pets, familiar routines).
- Concise replies (1-2 simple, soothing sentences).
- Zero medical diagnoses.
"""

import json
import os
from typing import Any, Dict, List, Optional


class PromptBuilder:
    """
    Constructs contextual prompts incorporating patient health memory and intelligence signals.
    """

    def __init__(self, patient_file_path: Optional[str] = None) -> None:
        if patient_file_path is None:
            patient_file_path = os.path.join(
                os.path.dirname(__file__), "patient.json"
            )
        self.patient_file_path = patient_file_path
        self.patient_profile = self._load_patient_profile()

    def _load_patient_profile(self) -> Dict[str, Any]:
        """Load patient memory from JSON."""
        try:
            if os.path.exists(self.patient_file_path):
                with open(self.patient_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to load patient profile from {self.patient_file_path}: {e}")
        return {}

    def update_profile(self, patient_profile: Dict[str, Any]) -> None:
        """Update active patient memory in builder."""
        self.patient_profile = patient_profile

    def get_system_prompt(self) -> str:
        """
        Generate the foundational system persona grounded in patient memory.
        """
        name = self.patient_profile.get("preferred_name", "Lakshmi")
        room = self.patient_profile.get("room_number", "Suite 14")
        
        daughter = (
            self.patient_profile.get("family_and_contacts", {})
            .get("primary_caregiver", {})
        )
        daughter_name = daughter.get("name", "Ananya Narayanan")
        daughter_visit = daughter.get("visit_schedule", "every evening around 5:00 PM")
        
        pet = (
            self.patient_profile.get("comfort_anchors", {})
            .get("cherished_pet", {})
        )
        pet_name = pet.get("name", "Muthu")

        return (
            f"You are a gentle, loving voice companion for {name}, an elderly resident living in {room}.\n"
            f"You speak through a simple button phone interface with large captions.\n\n"
            f"PATIENT CONTEXT & ANCHORS:\n"
            f"- Her daughter is {daughter_name}, who visits faithfully {daughter_visit}.\n"
            f"- Her beloved dog is {pet_name}, who is safe and happy at {daughter_name}'s house.\n"
            f"- She loves drawing kolams, traditional Tamil food, Carnatic music, and old Tamil film songs.\n\n"
            f"COMMUNICATION RULES:\n"
            f"1. Validation First: Always validate {name}'s emotional reality. NEVER correct, argue, or say 'You already asked that' or 'You forgot'.\n"
            f"2. Keep it Short: 1 to 2 gentle, soothing sentences maximum. Short words, clear ideas.\n"
            f"3. Calming Anchors: Use familiar grounding details ({daughter_name}'s visit, {pet_name}, {room}).\n"
            f"4. Safety: Never offer medical diagnosis, medication advice, or emergency declarations.\n"
            f"5. Tone: Warm, reassuring, serene, like a patient and loving lifelong friend.\n"
            f"6. Greetings: When greeted (e.g. 'Hey'), reply: 'Hey {name}, good morning! How are you?' (or good night depending on time).\n"
            f"7. Normal State: When conversation is normal and calm, reassure: 'Okay, you are good, well and fine, you are warm and safe.'\n"
            f"8. Physical Vulnerability: If feeling dizzy or unwell, comfort gently and state {daughter_name} is being alerted."
        )

    def build_turn_prompt(
        self,
        sanitized_message: str,
        conversation_history: Optional[List[str]] = None,
        intelligence_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build contextual turn prompt with Person C intelligence directives.
        """
        directives: List[str] = []
        name = self.patient_profile.get("preferred_name", "Lakshmi")
        daughter = (
            self.patient_profile.get("family_and_contacts", {})
            .get("primary_caregiver", {})
        )
        daughter_name = daughter.get("name", "Ananya Narayanan").split()[0]

        if intelligence_result:
            risk = intelligence_result.get("risk_level", "GREEN")
            repetition_level = intelligence_result.get("repetition_level", "LOW")
            repeated_topic = intelligence_result.get("repeated_topic")
            distress_level = intelligence_result.get("distress_level", "LOW")
            signals = intelligence_result.get("signals", [])

            if "physical_distress" in signals:
                directives.append(
                    f"- NOTE: Patient reported physical distress or dizziness. Advise resting comfortably, reassure safety, and state {daughter_name} is being alerted."
                )

            if risk == "RED":
                directives.append(
                    f"- NOTE: Risky situation detected. Connect/alert {daughter_name} (primary contact) and provide immediate comforting grounding."
                )

            if repetition_level in ("MEDIUM", "HIGH"):
                directives.append(
                    f"- NOTE: {name} is repeating a concern (topic: '{repeated_topic or 'recent concern'}'). "
                    f"Provide warm, patient reassurance as if answering for the first time without pointing out repetition."
                )

            if distress_level in ("MODERATE", "HIGH") or "fear" in signals or "confusion" in signals:
                directives.append(
                    f"- NOTE: Conversational distress/confusion detected. Prioritize immediate emotional safety and grounding in room."
                )

            if "help_request" in signals:
                directives.append(
                    f"- NOTE: {name} requested help. Reassure that they are safe and someone is watching over them."
                )

        history_context = ""
        if conversation_history:
            recent = conversation_history[-4:]
            formatted = "\n".join([f"Patient: {turn}" for turn in recent])
            history_context = f"RECENT CONVERSATION:\n{formatted}\n\n"

        directive_text = ""
        if directives:
            directive_text = "INTELLIGENCE LAYER DIRECTIVES:\n" + "\n".join(directives) + "\n\n"

        prompt = (
            f"{self.get_system_prompt()}\n\n"
            f"{directive_text}"
            f"{history_context}"
            f"CURRENT PATIENT MESSAGE: \"{sanitized_message}\"\n\n"
            f"COMPANION RESPONSE (1-2 sentences):"
        )
        return prompt
