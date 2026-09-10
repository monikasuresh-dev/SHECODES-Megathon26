import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app, escalation_manager, intelligence_engine


class TestEmotionalCompanion(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        intelligence_engine.reset()
        escalation_manager._alerts.clear()
        escalation_manager._recent_events.clear()

    def chat(self, message, history=None):
        response = self.client.post(
            "/chat",
            json={"message": message, "history": history or []},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_retrieves_indian_patient_memories(self):
        data = self.chat("What food do I like?")
        self.assertEqual(data["intelligence"]["intent"], "memory_retrieval")
        self.assertIn("idli", data["reply"].lower())
        self.assertIn("sambar", data["reply"].lower())

    def test_validates_loneliness_with_supportive_length(self):
        data = self.chat("Nobody is here with me.")
        self.assertEqual(data["intelligence"]["emotion"], "LONELY")
        self.assertGreaterEqual(len(data["reply"].split(". ")), 2)
        self.assertNotIn("already", data["reply"].lower())

    def test_repeated_memory_question_remains_patient(self):
        history = ["What is my name?", "What is my name?"]
        data = self.chat("What is my name?", history)
        self.assertEqual(data["intelligence"]["repetition_level"], "HIGH")
        self.assertIn("Lakshmi", data["reply"])
        self.assertNotIn("repeat", data["reply"].lower())

    def test_emergency_keeps_existing_escalation(self):
        data = self.chat("Please help me, I am terrified.")
        self.assertEqual(data["intelligence"]["emotion"], "EMERGENCY")
        self.assertEqual(data["intelligence"]["risk_level"], "RED")
        self.assertTrue(data["intelligence"]["escalate"])


if __name__ == "__main__":
    unittest.main()
