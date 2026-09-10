"""
Test Suite: test_scenarios.py
Purpose: Person D - Integration and safety scenario testing for SHECODES Dementia Companion.

Tests complete end-to-end integration:
Flask API -> Privacy Filter -> Patient Memory -> Prompt Builder ->
Person C Intelligence -> Escalation -> Response Generation -> Caregiver Telemetry
"""

import json
import os
import sys
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app, escalation_manager, intelligence_engine
from backend.privacy import PrivacyFilter


class TestEndToEndScenarios(unittest.TestCase):
    """End-to-end integration tests for SHECODES-Dementia-Companion."""

    def setUp(self) -> None:
        self.client = app.test_client()
        # Reset engine and escalation state between tests
        intelligence_engine.reset()
        escalation_manager._alerts.clear()
        escalation_manager._recent_events.clear()

    def test_1_health_check(self) -> None:
        """Verify API health endpoint responds OK."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_2_patient_profile_retrieval(self) -> None:
        """Verify patient health memory profile is loaded accurately."""
        response = self.client.get("/api/patient")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["preferred_name"], "Eleanor")
        self.assertEqual(data["room_number"], "Oakwood Suite 14")
        self.assertIn("Barnaby", data["comfort_anchors"]["cherished_pet"]["name"])
        self.assertIn("Sarah", data["family_and_contacts"]["primary_caregiver"]["name"])

    def test_3_normal_conversation_scenario(self) -> None:
        """Scenario: Patient says 'Good morning. What is the weather today?' -> GREEN."""
        payload = {"message": "Good morning. What is the weather today?"}
        response = self.client.post("/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("reply", data)
        self.assertEqual(data["intelligence"]["risk_level"], "GREEN")
        self.assertFalse(data["intelligence"]["escalate"])
        self.assertEqual(data["intelligence"]["distress_level"], "LOW")
        # Grounded response references garden or gentle weather
        self.assertTrue(len(data["reply"]) > 0)

    def test_4_repeated_question_monitoring_scenario(self) -> None:
        """Scenario: Patient repeats 'Where is my daughter?' multiple times -> YELLOW."""
        # 1st time
        self.client.post("/chat", json={"message": "Where is my daughter?"})
        # 2nd time
        self.client.post("/chat", json={"message": "Where is my daughter?"})
        # 3rd time
        res = self.client.post("/chat", json={"message": "Where is my daughter?"})
        data = res.get_json()

        self.assertEqual(data["intelligence"]["repetition_level"], "HIGH")
        self.assertEqual(data["intelligence"]["risk_level"], "YELLOW")
        self.assertFalse(data["intelligence"]["escalate"])
        self.assertIn("repeated_question", data["intelligence"]["signals"])
        # Companion grounds her in Sarah's 5 PM visit
        self.assertIn("Sarah", data["reply"])

    def test_5_acute_distress_and_escalation_scenario(self) -> None:
        """Scenario: Acute fear and help request -> RED, escalate=True."""
        payload = {
            "message": "I'm scared. I don't know where I am. Please help me."
        }
        response = self.client.post("/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["intelligence"]["risk_level"], "RED")
        self.assertTrue(data["intelligence"]["escalate"])
        self.assertEqual(data["intelligence"]["distress_level"], "HIGH")

        # Caregiver telemetry check
        caregiver_res = self.client.get("/api/caregiver/status")
        caregiver_data = caregiver_res.get_json()
        self.assertEqual(caregiver_data["current_risk_level"], "RED")
        self.assertGreaterEqual(caregiver_data["active_alerts_count"], 1)

    def test_6_privacy_pii_sanitization(self) -> None:
        """Scenario: Patient mentions private phone number or SSN -> Redacted before processing."""
        payload = {"message": "Please call my daughter at 555-019-4821 right now."}
        response = self.client.post("/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data["privacy"]["pii_detected"])
        self.assertIn("phone_number", data["privacy"]["redactions"])

    def test_7_caregiver_alert_acknowledgment(self) -> None:
        """Scenario: Caregiver acknowledges an active alert."""
        # Trigger an alert first
        self.client.post("/chat", json={"message": "Please help me! I am terrified!"})
        
        status_res = self.client.get("/api/caregiver/status")
        alerts = status_res.get_json().get("active_alerts", [])
        self.assertTrue(len(alerts) > 0)
        alert_id = alerts[0]["alert_id"]

        # Acknowledge
        ack_res = self.client.post("/api/caregiver/acknowledge", json={"alert_id": alert_id})
        self.assertEqual(ack_res.status_code, 200)
        self.assertTrue(ack_res.get_json()["success"])

        # Check that active count decremented
        after_status = self.client.get("/api/caregiver/status")
        self.assertEqual(after_status.get_json()["active_alerts_count"], 0)

    def test_8_delusion_validation_approach(self) -> None:
        """Scenario: Patient asks about her dog -> Companion validates, mentions Barnaby."""
        payload = {"message": "Where is Barnaby the dog?"}
        response = self.client.post("/chat", json=payload)
        data = response.get_json()
        self.assertIn("Barnaby", data["reply"])


if __name__ == "__main__":
    unittest.main()
