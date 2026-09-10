"""
Test Suite: test_call_session.py
Purpose: Verification and validation for WebRTC call signaling endpoints and CallSessionManager.

Covers:
- Call session creation
- Join as caregiver and patient
- Offer submission and retrieval
- Answer submission and retrieval
- ICE candidate exchange (caregiver and patient)
- End-session cleanup
- Missing / invalid session handling
- Duplicate join prevention
- Malformed payloads validation
"""

import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app
from backend.call_session import call_session_manager


class TestCallSessionSignaling(unittest.TestCase):
    """Integration tests for WebRTC call signaling endpoints."""

    def setUp(self) -> None:
        self.client = app.test_client()
        with call_session_manager._lock:
            call_session_manager._sessions.clear()

    def test_1_create_call_session(self) -> None:
        """Verify call session creation endpoint."""
        res = self.client.post("/api/call/session", json={"patient_id": "PATIENT-84920"})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("session_id", data)
        self.assertEqual(data["status"], "WAITING")
        self.assertEqual(data["patient_id"], "PATIENT-84920")
        self.assertFalse(data["caregiver_joined"])
        self.assertFalse(data["has_offer"])

    def test_2_get_active_session(self) -> None:
        """Verify active session retrieval."""
        self.client.post("/api/call/session", json={"patient_id": "PATIENT-84920"})
        res = self.client.get("/api/call/session/active?patient_id=PATIENT-84920")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data["session"])
        self.assertEqual(data["session"]["status"], "WAITING")

    def test_3_join_session(self) -> None:
        """Verify caregiver and patient can join."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        # Caregiver join
        res_cg = self.client.post(f"/api/call/session/{session_id}/join", json={"role": "caregiver"})
        self.assertEqual(res_cg.status_code, 200)
        self.assertTrue(res_cg.get_json()["session"]["caregiver_joined"])

        # Patient join
        res_pt = self.client.post(f"/api/call/session/{session_id}/join", json={"role": "patient"})
        self.assertEqual(res_pt.status_code, 200)
        self.assertTrue(res_pt.get_json()["session"]["patient_joined"])

    def test_4_submit_offer(self) -> None:
        """Verify caregiver submits offer."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        offer_payload = {
            "offer": {"type": "offer", "sdp": "v=0\r\no=caregiver 123 456..."},
            "role": "caregiver",
        }
        res_offer = self.client.post(f"/api/call/session/{session_id}/offer", json=offer_payload)
        self.assertEqual(res_offer.status_code, 200)
        data = res_offer.get_json()
        self.assertTrue(data["session"]["has_offer"])
        self.assertEqual(data["session"]["status"], "CONNECTING")

    def test_5_submit_answer(self) -> None:
        """Verify patient submits answer after offer."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        offer_payload = {
            "offer": {"type": "offer", "sdp": "v=0\r\no=caregiver 123 456..."},
            "role": "caregiver",
        }
        self.client.post(f"/api/call/session/{session_id}/offer", json=offer_payload)

        answer_payload = {
            "answer": {"type": "answer", "sdp": "v=0\r\no=patient 789 012..."},
            "role": "patient",
        }
        res_ans = self.client.post(f"/api/call/session/{session_id}/answer", json=answer_payload)
        self.assertEqual(res_ans.status_code, 200)
        data = res_ans.get_json()
        self.assertTrue(data["session"]["has_answer"])
        self.assertEqual(data["session"]["status"], "CONNECTED")

    def test_6_ice_candidate_exchange(self) -> None:
        """Verify exchanging ICE candidates for both roles."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        # Caregiver ICE
        cg_candidate = {"candidate": "candidate:1 1 UDP 2122260223 192.168.1.5 5000 typ host", "sdpMid": "0"}
        res_cg_ice = self.client.post(
            f"/api/call/session/{session_id}/ice",
            json={"candidate": cg_candidate, "role": "caregiver"},
        )
        self.assertEqual(res_cg_ice.status_code, 200)
        self.assertEqual(res_cg_ice.get_json()["count"], 1)

        # Patient ICE
        pt_candidate = {"candidate": "candidate:2 1 UDP 2122260223 192.168.1.6 5001 typ host", "sdpMid": "0"}
        res_pt_ice = self.client.post(
            f"/api/call/session/{session_id}/ice",
            json={"candidate": pt_candidate, "role": "patient"},
        )
        self.assertEqual(res_pt_ice.status_code, 200)
        self.assertEqual(res_pt_ice.get_json()["count"], 1)

        # Retrieve and verify both candidates in session state
        res_get = self.client.get(f"/api/call/session/{session_id}")
        session_data = res_get.get_json()
        self.assertEqual(len(session_data["caregiver_ice_candidates"]), 1)
        self.assertEqual(len(session_data["patient_ice_candidates"]), 1)

    def test_7_end_session(self) -> None:
        """Verify ending session and clean state."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        res_end = self.client.post(f"/api/call/session/{session_id}/end", json={"role": "caregiver"})
        self.assertEqual(res_end.status_code, 200)
        self.assertEqual(res_end.get_json()["session"]["status"], "ENDED")
        self.assertEqual(res_end.get_json()["session"]["ended_by"], "caregiver")

        # Verify it is no longer returned as active
        res_active = self.client.get("/api/call/session/active")
        self.assertIsNone(res_active.get_json()["session"])

    def test_8_invalid_session_returns_404(self) -> None:
        """Verify unknown session ID returns 404."""
        res = self.client.get("/api/call/session/nonexistent_123")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())

    def test_9_duplicate_join_rejected(self) -> None:
        """Verify joining twice with same role is rejected with 400."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        self.client.post(f"/api/call/session/{session_id}/join", json={"role": "caregiver"})
        res_dup = self.client.post(f"/api/call/session/{session_id}/join", json={"role": "caregiver"})
        self.assertEqual(res_dup.status_code, 400)
        self.assertIn("already joined", res_dup.get_json()["error"])

    def test_10_malformed_payloads_rejected(self) -> None:
        """Verify invalid/missing payload fields return 400."""
        res_create = self.client.post("/api/call/session", json={})
        session_id = res_create.get_json()["session_id"]

        # Offer without 'offer' dict
        res_bad_offer = self.client.post(
            f"/api/call/session/{session_id}/offer",
            json={"role": "caregiver"},
        )
        self.assertEqual(res_bad_offer.status_code, 400)

        # Offer with malformed dictionary (missing sdp)
        res_bad_offer2 = self.client.post(
            f"/api/call/session/{session_id}/offer",
            json={"offer": {"type": "offer"}, "role": "caregiver"},
        )
        self.assertEqual(res_bad_offer2.status_code, 400)

        # ICE without role
        res_bad_ice = self.client.post(
            f"/api/call/session/{session_id}/ice",
            json={"candidate": {}},
        )
        self.assertEqual(res_bad_ice.status_code, 400)


if __name__ == "__main__":
    unittest.main()
