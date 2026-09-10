"""
Module: test_red_webrtc_integration.py
Purpose: Integration tests for Phase 4:
         RED escalation -> Caregiver Alert -> WebRTC Call Session association and lifecycle.
"""

import json
import unittest

from backend.app import app, call_session_manager, escalation_manager, intelligence_engine


class TestRedWebRtcIntegration(unittest.TestCase):
    """
    Validates end-to-end integration between RED distress detection,
    caregiver alerts, and WebRTC call session lifecycle.
    """

    def setUp(self):
        self.client = app.test_client()
        intelligence_engine.reset()
        call_session_manager._sessions.clear()
        escalation_manager._alerts.clear()
        escalation_manager._recent_events.clear()

    def test_1_red_creates_caregiver_alert(self):
        """1. Verify RED risk level creates an active caregiver alert."""
        res = self.client.post(
            "/chat",
            data=json.dumps({"message": "I'm terrified, someone is breaking in! Please help me!"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["intelligence"]["risk_level"], "RED")

        status_res = self.client.get("/api/caregiver/status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertGreaterEqual(status_data["active_alerts_count"], 1)
        latest_alert = status_data["active_alerts"][0]
        self.assertEqual(latest_alert["risk_level"], "RED")
        self.assertEqual(latest_alert["status"], "ACTIVE")

    def test_2_red_creates_one_waiting_call_session(self):
        """2. Verify RED risk level creates a single WAITING WebRTC call session."""
        res = self.client.post(
            "/chat",
            data=json.dumps({"message": "I am so scared! Help me! The stranger is in my room!"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

        active_res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        self.assertEqual(active_res.status_code, 200)
        active_data = active_res.get_json()
        session = active_data.get("session")
        self.assertIsNotNone(session)
        self.assertEqual(session["status"], "WAITING")
        self.assertFalse(session["caregiver_joined"])
        self.assertFalse(session["patient_joined"])
        self.assertFalse(session["has_offer"])
        self.assertIsNotNone(session.get("alert_id"))

        status_res = self.client.get("/api/caregiver/status")
        status_data = status_res.get_json()
        alert = status_data["active_alerts"][0]
        self.assertEqual(alert["session_id"], session["session_id"])

    def test_3_repeated_red_does_not_create_duplicate_sessions(self):
        """3. Verify multiple consecutive RED interactions reuse existing waiting session."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "I am terrified! Help me!"}),
            content_type="application/json",
        )
        active_res1 = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        session1 = active_res1.get_json()["session"]
        first_session_id = session1["session_id"]

        self.client.post(
            "/chat",
            data=json.dumps({"message": "Please hurry, somebody is trying to hurt me!"}),
            content_type="application/json",
        )
        active_res2 = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        session2 = active_res2.get_json()["session"]

        self.assertEqual(session2["session_id"], first_session_id)
        self.assertEqual(len([s for s in call_session_manager._sessions.values() if s.is_active()]), 1)

    def test_4_green_does_not_create_call_session(self):
        """4. Verify standard GREEN interactions do not create a WebRTC call session."""
        res = self.client.post(
            "/chat",
            data=json.dumps({"message": "Good morning, what a lovely sunny day today."}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["intelligence"]["risk_level"], "GREEN")

        active_res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        self.assertEqual(active_res.status_code, 200)
        self.assertIsNone(active_res.get_json()["session"])

    def test_5_yellow_does_not_create_call_session(self):
        """5. Verify YELLOW repeated question does not create a WebRTC call session."""
        self.client.post("/chat", json={"message": "Where is my daughter?"})
        self.client.post("/chat", json={"message": "Where is my daughter?"})
        res = self.client.post("/chat", json={"message": "Where is my daughter?"})
        data = res.get_json()
        self.assertEqual(data["intelligence"]["risk_level"], "YELLOW")

        active_res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        self.assertEqual(active_res.status_code, 200)
        self.assertIsNone(active_res.get_json()["session"])

    def test_6_caregiver_can_retrieve_waiting_session(self):
        """6. Verify caregiver dashboard status exposes the active waiting call session."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "Help me, I am panicking and don't know where I am!"}),
            content_type="application/json",
        )
        status_res = self.client.get("/api/caregiver/status")
        self.assertEqual(status_res.status_code, 200)
        data = status_res.get_json()

        active_call = data.get("active_call_session")
        self.assertIsNotNone(active_call)
        self.assertEqual(active_call["status"], "WAITING")
        self.assertTrue(active_call["session_id"].startswith("call_"))

    def test_7_caregiver_can_join_session(self):
        """7. Verify caregiver can join the waiting session created by RED."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "Help me please, I am so afraid!"}),
            content_type="application/json",
        )
        active_res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        session_id = active_res.get_json()["session"]["session_id"]

        join_res = self.client.post(
            f"/api/call/session/{session_id}/join",
            data=json.dumps({"role": "caregiver"}),
            content_type="application/json",
        )
        self.assertEqual(join_res.status_code, 200)
        session_data = join_res.get_json()["session"]
        self.assertTrue(session_data["caregiver_joined"])

    def test_8_alert_acknowledgement_remains_separate_from_webrtc(self):
        """8. Verify alert acknowledgment does not terminate or join WebRTC call session."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "I'm scared. I don't know where I am. Please help me."}),
            content_type="application/json",
        )
        status_res = self.client.get("/api/caregiver/status")
        alert = status_res.get_json()["active_alerts"][0]
        alert_id = alert["alert_id"]
        session_id = alert["session_id"]

        ack_res = self.client.post(
            "/api/caregiver/acknowledge",
            data=json.dumps({"alert_id": alert_id}),
            content_type="application/json",
        )
        self.assertEqual(ack_res.status_code, 200)
        self.assertTrue(ack_res.get_json()["success"])

        session_res = self.client.get(f"/api/call/session/{session_id}")
        self.assertEqual(session_res.status_code, 200)
        session_data = session_res.get_json()
        self.assertEqual(session_data["status"], "WAITING")
        self.assertFalse(session_data["caregiver_joined"])

    def test_9_call_session_transitions_to_active(self):
        """9. Verify session transitions through WAITING -> CONNECTING -> CONNECTED."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "Help me! I am terrified!"}),
            content_type="application/json",
        )
        active_res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        session_id = active_res.get_json()["session"]["session_id"]

        self.client.post(
            f"/api/call/session/{session_id}/join",
            data=json.dumps({"role": "caregiver"}),
            content_type="application/json",
        )

        offer_res = self.client.post(
            f"/api/call/session/{session_id}/offer",
            data=json.dumps({"offer": {"type": "offer", "sdp": "v=0\r\no=caregiver 123..."}, "role": "caregiver"}),
            content_type="application/json",
        )
        self.assertEqual(offer_res.status_code, 200)
        self.assertEqual(offer_res.get_json()["session"]["status"], "CONNECTING")

        self.client.post(
            f"/api/call/session/{session_id}/join",
            data=json.dumps({"role": "patient"}),
            content_type="application/json",
        )

        answer_res = self.client.post(
            f"/api/call/session/{session_id}/answer",
            data=json.dumps({"answer": {"type": "answer", "sdp": "v=0\r\no=patient 456..."}, "role": "patient"}),
            content_type="application/json",
        )
        self.assertEqual(answer_res.status_code, 200)
        self.assertEqual(answer_res.get_json()["session"]["status"], "CONNECTED")

    def test_10_ended_session_is_not_reused(self):
        """10. Verify an ended session is not reused when a new RED event occurs."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "Help me! Someone is at my window!"}),
            content_type="application/json",
        )
        session_1 = self.client.get("/api/call/session/active?patient_id=PATIENT-84920").get_json()["session"]
        session_id_1 = session_1["session_id"]

        end_res = self.client.post(
            f"/api/call/session/{session_id_1}/end",
            data=json.dumps({"role": "caregiver"}),
            content_type="application/json",
        )
        self.assertEqual(end_res.status_code, 200)
        self.assertEqual(end_res.get_json()["session"]["status"], "ENDED")

        active_after_end = self.client.get("/api/call/session/active?patient_id=PATIENT-84920").get_json()["session"]
        self.assertIsNone(active_after_end)

        self.client.post(
            "/chat",
            data=json.dumps({"message": "I am scared again! Help me!"}),
            content_type="application/json",
        )
        session_2 = self.client.get("/api/call/session/active?patient_id=PATIENT-84920").get_json()["session"]
        self.assertIsNotNone(session_2)
        self.assertNotEqual(session_2["session_id"], session_id_1)
        self.assertEqual(session_2["status"], "WAITING")

    def test_11_existing_intelligence_tests_contract(self):
        """11. Verify intelligence result contract remains intact inside /chat response."""
        res = self.client.post(
            "/chat",
            data=json.dumps({"message": "Can you tell me a happy memory about Barnaby?"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("reply", data)
        self.assertIn("intelligence", data)
        self.assertIn("privacy", data)
        self.assertIn("patient", data)
        intel = data["intelligence"]
        for key in ("distress_score", "risk_level", "repetition_count", "reason", "signals", "escalate"):
            self.assertIn(key, intel)

    def test_12_existing_scenario_contract(self):
        """12. Verify caregiver status response structure matches expected contract."""
        res = self.client.get("/api/caregiver/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("current_risk_level", data)
        self.assertIn("current_distress_score", data)
        self.assertIn("active_alerts_count", data)
        self.assertIn("active_alerts", data)
        self.assertIn("recent_events", data)
        self.assertIn("patient", data)
        self.assertIn("active_call_session", data)

    def test_13_existing_signaling_contract(self):
        """13. Verify WebRTC signaling endpoints function under the integration."""
        create_res = self.client.post("/api/call/session", json={"patient_id": "PATIENT-84920"})
        self.assertEqual(create_res.status_code, 201)
        s_id = create_res.get_json()["session_id"]

        ice_res = self.client.post(
            f"/api/call/session/{s_id}/ice",
            json={"candidate": {"candidate": "candidate:1 1 UDP ..."}, "role": "caregiver"},
        )
        self.assertEqual(ice_res.status_code, 200)
        self.assertTrue(ice_res.get_json()["success"])

    def test_14_malformed_session_state_does_not_crash(self):
        """14. Verify malformed payloads to signaling endpoints return 400 without crashing."""
        self.client.post(
            "/chat",
            data=json.dumps({"message": "I'm scared. I don't know where I am. Please help me."}),
            content_type="application/json",
        )
        active = self.client.get("/api/call/session/active?patient_id=PATIENT-84920").get_json()["session"]
        s_id = active["session_id"]

        bad_offer = self.client.post(f"/api/call/session/{s_id}/offer", data="not json", content_type="text/plain")
        self.assertEqual(bad_offer.status_code, 400)

        bad_join = self.client.post(f"/api/call/session/{s_id}/join", data="", content_type="application/json")
        self.assertEqual(bad_join.status_code, 400)

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
