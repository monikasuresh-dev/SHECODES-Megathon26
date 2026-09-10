"""
Test Suite: test_aadil_companion_requirements.py
Purpose: Test the new personalized companion requirements:
1. Time-aware personalized greeting ("Hey Aadil, [time_greeting]! How are you?")
2. Physical distress / dizziness -> RED escalation redirect to caregiver + live WebRTC call
3. Normal situation -> "Okay, you are good, well and fine, you are warm and safe."
4. Repetition of "My daughter, my daughter, my daughter, my daughter, my daughter" -> RED redirect to caregiver
5. Risky situations connect to close contact (primary caregiver Sarah Higgins).
"""

import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app, escalation_manager, intelligence_engine, patient_profile, static_responder, prompt_builder
from backend.static_responses import get_time_greeting


class TestAadilCompanionRequirements(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        intelligence_engine.reset()
        escalation_manager._alerts.clear()
        escalation_manager._recent_events.clear()
        patient_profile["preferred_name"] = "Eleanor"
        patient_profile["name"] = "Eleanor Higgins"
        static_responder.update_profile(patient_profile)
        prompt_builder.update_profile(patient_profile)

    def test_1_greeting_with_aadil_name_and_time(self):
        """When user says 'Hey, my name is Aadil', it replies 'Hey Aadil, [time]! How are you?'."""
        res = self.client.post("/chat", json={"message": "Hey, my name is Aadil"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        time_greet = get_time_greeting()
        expected = f"Hey Aadil, {time_greet}! How are you?"
        self.assertEqual(data["reply"], expected)
        self.assertEqual(data["patient"]["name"], "Aadil")

        # Subsequent greeting "Hey" remembers name Aadil
        res2 = self.client.post("/chat", json={"message": "Hey"})
        data2 = res2.get_json()
        self.assertEqual(data2["reply"], expected)

    def test_2_physical_distress_and_dizziness_redirects_caregiver(self):
        """If patient is not feeling well and feeling a bit of dizzy -> RED + alerts caregiver."""
        res = self.client.post("/chat", json={
            "message": "I'm not feeling well and I'm feeling a bit of dizzy"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Risk level RED and escalated
        self.assertEqual(data["intelligence"]["risk_level"], "RED")
        self.assertTrue(data["intelligence"]["escalate"])
        self.assertIn("physical_distress", data["intelligence"]["signals"])

        # Companion comforting reply mentioning Sarah (primary caregiver)
        self.assertIn("Sarah", data["reply"])
        self.assertIn("rest", data["reply"].lower())

        # Caregiver alert and WebRTC session
        status_res = self.client.get("/api/caregiver/status")
        caregiver_data = status_res.get_json()
        self.assertEqual(caregiver_data["current_risk_level"], "RED")
        self.assertIsNotNone(caregiver_data["active_call_session"])
        self.assertEqual(caregiver_data["active_call_session"]["status"], "WAITING")

    def test_3_normal_conversation_returns_warm_and_safe(self):
        """When situation is normal, returns 'Okay, you are good, well and fine, you are warm and safe.'"""
        res = self.client.post("/chat", json={"message": "I am just resting in my chair today."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["intelligence"]["risk_level"], "GREEN")
        self.assertFalse(data["intelligence"]["escalate"])
        self.assertEqual(data["reply"], "Okay, you are good, well and fine, you are warm and safe.")

    def test_4_repeated_my_daughter_five_times_escalates_red(self):
        """'My daughter, my daughter, my daughter, my daughter, my daughter' -> RED + redirect caregiver."""
        res = self.client.post("/chat", json={
            "message": "My daughter, my daughter, my daughter, my daughter, my daughter"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Severe repetition triggers RED
        self.assertEqual(data["intelligence"]["risk_level"], "RED")
        self.assertTrue(data["intelligence"]["escalate"])
        self.assertGreaterEqual(data["intelligence"]["repetition_count"], 5)
        self.assertEqual(data["intelligence"]["repeated_topic"], "daughter")

        # Live session created for caregiver
        status_res = self.client.get("/api/caregiver/status")
        caregiver_data = status_res.get_json()
        self.assertIsNotNone(caregiver_data["active_call_session"])

        # Grounding reply mentions connecting with Sarah
        self.assertIn("connecting you with Sarah", data["reply"])

    def test_5_risky_situation_connects_to_close_person_in_list(self):
        """Risky situation connects live session to Sarah Higgins (primary caregiver on list)."""
        res = self.client.post("/chat", json={
            "message": "I am terrified! Somebody please help me!"
        })
        data = res.get_json()
        self.assertEqual(data["intelligence"]["risk_level"], "RED")
        self.assertTrue(data["intelligence"]["escalate"])

        status_res = self.client.get("/api/caregiver/status")
        caregiver_data = status_res.get_json()
        primary_caregiver = caregiver_data["patient"]["primary_caregiver"]
        self.assertEqual(primary_caregiver["name"], "Sarah Higgins")
        self.assertEqual(primary_caregiver["relationship"], "Daughter")


if __name__ == "__main__":
    unittest.main()
