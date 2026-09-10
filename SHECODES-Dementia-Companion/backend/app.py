"""
Module: app.py
Purpose: Person B - Main Flask API Application integrating Person C Intelligence,
Person D Privacy, Patient Memory, and Frontends.

Connects:
Frontend / Button Phone UI
      ↓
POST /chat
      ↓
Privacy Filter (privacy.py)
      ↓
Person C Intelligence (repetition.py, distress.py, escalation.py)
      ↓
Response Generator (Gemini API or patient-grounded static fallback)
      ↓
Escalation & Caregiver Timeline Recording
      ↓
Structured JSON Response
      ↓
Frontend + Caregiver Dashboard
"""

import json
import os
import re
import sys
from typing import Any, Dict, Optional
import urllib.error
import urllib.request
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.privacy import PrivacyFilter
from backend.repetition import RepetitionTracker
from backend.distress import DistressScorer
from backend.escalation import EscalationManager
from backend.intelligence import IntelligenceEngine
from backend.prompt import PromptBuilder
from backend.static_responses import StaticResponseGenerator
from backend.call_session import call_session_manager

# Optional dotenv loading
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

# Flask application setup
app = Flask(__name__)

# Enable CORS for all routes (Person A frontend compatibility)
try:
    from flask_cors import CORS
    CORS(app, origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://172.17.152.64:5000",
    ])
except ImportError:
    # Manual CORS headers fallback if flask_cors is not installed
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response


# ==============================================================================
# INITIALIZE BACKEND SERVICES
# ==============================================================================

privacy_filter = PrivacyFilter()
prompt_builder = PromptBuilder()
patient_profile = prompt_builder.patient_profile
patient_connection_lock = threading.Lock()
patient_connection = {
    "patient_id": patient_profile.get("patient_id", "PATIENT-84920"),
    "last_seen": None,
    "source": None,
}
PATIENT_HEARTBEAT_TIMEOUT_SECONDS = 15
static_responder = StaticResponseGenerator(patient_profile=patient_profile)
escalation_manager = EscalationManager()

intelligence_engine = IntelligenceEngine(
    conversation_id="eleanor_session",
    escalation_manager=escalation_manager,
)

# Optional Gemini API Client
gemini_client = None
gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if gemini_api_key:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=gemini_api_key)
        print("[Info] Google Gemini Client successfully initialized.")
    except Exception as e:
        print(f"[Info] Running with offline grounded responder: {e}")


COMMON_NON_NAMES = {
    "terrified", "frightened", "scared", "afraid", "lost", "confused",
    "dizzy", "fine", "okay", "good", "sick", "panicking", "worried",
    "in", "at", "not", "here", "ready", "sorry", "tired", "back", "home",
    "alone", "trying", "feeling", "well", "great", "bad", "terrible",
    "better", "worse", "trouble", "pain", "faint", "help", "someone",
    "somebody", "there", "myself", "sure", "wondering", "just", "so",
    "very", "a", "an", "the", "old", "dying", "hurting", "hurt", "bleeding",
    "choking", "freezing", "cold", "warm", "hot", "hungry", "thirsty",
    "sitting", "standing", "lying", "awake", "asleep", "leaving", "going"
}


def detect_and_update_name(raw_text: str, payload_data: Dict[str, Any]) -> None:
    """Detect if patient introduces themselves by name or supplies name in payload."""
    if "preferred_name" in payload_data and payload_data["preferred_name"]:
        new_name = str(payload_data["preferred_name"]).strip()
        patient_profile["preferred_name"] = new_name
        patient_profile["name"] = new_name
        static_responder.update_profile(patient_profile)
        prompt_builder.update_profile(patient_profile)
        return

    if "name" in payload_data and payload_data["name"]:
        new_name = str(payload_data["name"]).strip()
        patient_profile["name"] = new_name
        patient_profile["preferred_name"] = new_name.split()[0]
        static_responder.update_profile(patient_profile)
        prompt_builder.update_profile(patient_profile)
        return

    name_match = re.search(
        r"\b(?:my name is|name is|call me)\s+([A-Za-z]+)\b",
        raw_text,
        re.IGNORECASE,
    )
    if not name_match:
        intro_match = re.search(
            r"\b(?:i am|i'm|this is)\s+([A-Za-z]+)\b",
            raw_text,
            re.IGNORECASE,
        )
        if intro_match:
            cand = intro_match.group(1).lower()
            if (
                cand not in COMMON_NON_NAMES
                and not cand.endswith(("ed", "ing", "ful", "less", "able", "ive", "y"))
                and len(cand) >= 2
            ):
                name_match = intro_match

    if name_match:
        cand = name_match.group(1).strip()
        if cand.lower() not in COMMON_NON_NAMES and len(cand) >= 2:
            formatted_name = cand.capitalize()
            patient_profile["preferred_name"] = formatted_name
            patient_profile["name"] = formatted_name
            static_responder.update_profile(patient_profile)
            prompt_builder.update_profile(patient_profile)


def mark_patient_seen(source: str = "patient") -> Dict[str, Any]:
    """Update backend-owned patient presence; never rely on browser storage."""
    now = datetime.now(timezone.utc)
    with patient_connection_lock:
        patient_connection["last_seen"] = now
        patient_connection["source"] = source
    print(f"[PATIENT] {'Heartbeat received' if source == 'heartbeat' else 'Connected'}")
    return get_patient_connection()


def get_patient_connection() -> Dict[str, Any]:
    with patient_connection_lock:
        last_seen = patient_connection["last_seen"]
        source = patient_connection["source"]
        patient_id = patient_connection["patient_id"]
    online = bool(last_seen and (datetime.now(timezone.utc) - last_seen).total_seconds() <= PATIENT_HEARTBEAT_TIMEOUT_SECONDS)
    return {
        "patient_id": patient_id,
        "online": online,
        "status": "ONLINE" if online else "OFFLINE",
        "last_seen": last_seen.isoformat() if last_seen else None,
        "source": source,
    }


def call_gemini_rest_api(turn_prompt: str, api_key: str) -> Optional[str]:
    """Call Google Gemini 2.5 Flash endpoint via REST without external SDK dependencies."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": turn_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 120,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
    except Exception as e:
        print(f"[Info] Gemini REST call skipped/fallback: {e}")
    return None


def generate_llm_reply(
    sanitized_message: str,
    conversation_history: Optional[list],
    intelligence_result: Dict[str, Any],
) -> str:
    """
    Generate conversational reply via Gemini API if configured,
    or use patient-grounded static fallback.
    """
    if gemini_api_key:
        try:
            turn_prompt = prompt_builder.build_turn_prompt(
                sanitized_message=sanitized_message,
                conversation_history=conversation_history,
                intelligence_result=intelligence_result,
            )
            # Try REST API (works without google-genai package)
            rest_reply = call_gemini_rest_api(turn_prompt, gemini_api_key)
            if rest_reply:
                return rest_reply

            # Try SDK client if available
            if gemini_client:
                response = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=turn_prompt,
                )
                if response and response.text:
                    return response.text.strip()
        except Exception as e:
            print(f"[Warning] Gemini API call failed, using grounded fallback: {e}")

    # Grounded offline fallback
    return static_responder.generate_response(
        sanitized_message=sanitized_message,
        intelligence_result=intelligence_result,
    )


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.route("/chat", methods=["POST"])
def chat():
    """
    Main conversational interaction endpoint.
    
    Accepts:
        {
            "message": "Where is my daughter?",
            "history": ["optional prior messages"]
        }
    """
    data = request.get_json(silent=True) or {}
    raw_message = data.get("message", "")
    history = data.get("history", None)
    mark_patient_seen("message")
    print("[PATIENT] Message received")

    # 0. Dynamic patient profile / name update
    detect_and_update_name(raw_message, data)

    # 1. Privacy filtering (Person D)
    privacy_res = privacy_filter.filter_text(raw_message)
    sanitized_message = privacy_res["sanitized_text"]

    # 2. Intelligence Layer: Repetition, Distress, Risk, Escalation (Person C)
    intelligence_res = intelligence_engine.process_message(
        patient_message=sanitized_message,
        conversation_history=history,
    )

    # 3. Response Generation (Person B)
    reply = generate_llm_reply(
        sanitized_message=sanitized_message,
        conversation_history=history,
        intelligence_result=intelligence_res,
    )

    # 4. Record event for Caregiver Dashboard & generate alert if escalated
    patient_id = patient_profile.get("patient_id", "PATIENT-84920")
    alert_record = escalation_manager.record_interaction(
        patient_message=sanitized_message,
        reply=reply,
        intelligence_result=intelligence_res,
        patient_id=patient_id,
    )

    # 4b. Phase 4: RED escalation -> create or reuse waiting WebRTC call session
    if intelligence_res.get("risk_level") == "RED" or intelligence_res.get("escalate"):
        existing_session = call_session_manager.get_active_session(patient_id=patient_id)
        if existing_session and existing_session.is_active():
            active_call_session = existing_session
        else:
            alert_id = alert_record.get("alert_id") if alert_record else None
            active_call_session = call_session_manager.create_session(
                patient_id=patient_id,
                alert_id=alert_id,
            )
        if alert_record and active_call_session:
            alert_record["session_id"] = active_call_session.session_id

    # 5. Return structured JSON matching all team contracts
    return jsonify({
        "reply": reply,
        "intelligence": intelligence_res,
        "privacy": {
            "pii_detected": privacy_res["pii_detected"],
            "redactions": privacy_res["redactions"],
            "safety_warning": privacy_res["safety_warning"],
        },
        "patient": {
            "name": patient_profile.get("preferred_name", "Lakshmi"),
            "room": patient_profile.get("room_number", "Suite 14"),
        },
    }), 200


@app.route("/api/patient", methods=["GET", "POST", "PUT"])
def get_patient():
    """Returns or updates persistent patient memory profile."""
    if request.method in ["POST", "PUT"]:
        data = request.get_json(silent=True) or {}
        if "preferred_name" in data and data["preferred_name"]:
            patient_profile["preferred_name"] = str(data["preferred_name"]).strip()
        if "name" in data and data["name"]:
            patient_profile["name"] = str(data["name"]).strip()
            if "preferred_name" not in data:
                patient_profile["preferred_name"] = patient_profile["name"].split()[0]
        for k, v in data.items():
            if k not in ["preferred_name", "name"]:
                patient_profile[k] = v
        static_responder.update_profile(patient_profile)
        prompt_builder.update_profile(patient_profile)
        return jsonify(patient_profile), 200
    return jsonify(patient_profile), 200


@app.route("/api/patient/heartbeat", methods=["POST"])
def patient_heartbeat():
    """Record a patient phone heartbeat for caregiver presence monitoring."""
    data = request.get_json(silent=True) or {}
    expected_id = patient_profile.get("patient_id", "PATIENT-84920")
    requested_id = str(data.get("patient_id", expected_id))
    if requested_id != expected_id:
        return jsonify({"error": "Unknown patient_id"}), 400
    connection = mark_patient_seen("heartbeat")
    print("[BACKEND] Patient state updated")
    return jsonify({"success": True, "connection": connection, "patient": {
        "patient_id": expected_id,
        "name": patient_profile.get("name", "Lakshmi Narayanan"),
    }}), 200


@app.route("/api/caregiver/status", methods=["GET"])
def get_caregiver_status():
    """Returns real-time dashboard data for the caregiver interface."""
    summary = escalation_manager.get_dashboard_summary()
    patient_id = patient_profile.get("patient_id", "PATIENT-84920")
    active_call = call_session_manager.get_active_session(patient_id=patient_id)
    summary["active_call_session"] = active_call.to_dict() if active_call else None
    summary["patient"] = {
        "name": patient_profile.get("name", "Lakshmi Narayanan"),
        "preferred_name": patient_profile.get("preferred_name", "Lakshmi"),
        "age": patient_profile.get("age", 72),
        "condition": patient_profile.get("condition", "Mild Dementia"),
        "room_number": patient_profile.get("room_number", "Anna Nagar, Chennai"),
        "primary_caregiver": patient_profile.get("family_and_contacts", {}).get("primary_caregiver", {}),
        "connection": get_patient_connection(),
    }
    print(f"[CAREGIVER] Patient update sent ({summary['patient']['connection']['status']})")
    return jsonify(summary), 200


@app.route("/api/caregiver/acknowledge", methods=["POST"])
def acknowledge_alert():
    """Allows caregiver to acknowledge an active alert."""
    data = request.get_json(silent=True) or {}
    alert_id = data.get("alert_id")
    if not alert_id:
        return jsonify({"error": "Missing alert_id"}), 400
    
    success = escalation_manager.acknowledge_alert(alert_id)
    return jsonify({"success": success, "alert_id": alert_id}), 200


@app.route("/api/health", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "SHECODES-Dementia-Companion-Backend",
        "version": "1.0.0",
        "gemini_active": gemini_client is not None,
    }), 200


# ==============================================================================
# WEBRTC CALL SIGNALING APIS (CAREGIVER <-> PATIENT LIVE SESSION)
# ==============================================================================

@app.route("/api/call/session", methods=["POST"])
def create_call_session():
    """Create or reset a WebRTC call session."""
    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id", patient_profile.get("patient_id", "PATIENT-84920"))
    session_id = data.get("session_id")
    alert_id = data.get("alert_id")
    session = call_session_manager.create_session(patient_id=patient_id, session_id=session_id, alert_id=alert_id)
    return jsonify(session.to_dict()), 201


@app.route("/api/call/session/active", methods=["GET"])
def get_active_call_session():
    """Get currently active or waiting call session."""
    patient_id = request.args.get("patient_id", patient_profile.get("patient_id", "PATIENT-84920"))
    session = call_session_manager.get_active_session(patient_id=patient_id)
    if not session:
        return jsonify({"session": None}), 200
    return jsonify({"session": session.to_dict()}), 200


@app.route("/api/call/session/<session_id>", methods=["GET"])
def get_call_session(session_id):
    """Get current session state."""
    session = call_session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.to_dict()), 200


@app.route("/api/call/session/<session_id>/join", methods=["POST"])
def join_call_session(session_id):
    """Caregiver or patient joins the call session."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON payload"}), 400
    role = data.get("role", "caregiver")
    success, err_msg, session = call_session_manager.join_session(session_id, role=role)
    if not success:
        status_code = 404 if err_msg == "Session not found" else 400
        return jsonify({"error": err_msg}), status_code
    return jsonify({"success": True, "session": session.to_dict()}), 200


@app.route("/api/call/session/<session_id>/offer", methods=["POST"])
def submit_call_offer(session_id):
    """Submit WebRTC SDP offer."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON payload"}), 400
    offer = data.get("offer")
    role = data.get("role", "caregiver")
    if not offer:
        return jsonify({"error": "Missing 'offer' in request body"}), 400
    success, err_msg, session = call_session_manager.set_offer(session_id, offer=offer, role=role)
    if not success:
        status_code = 404 if err_msg == "Session not found" else 400
        return jsonify({"error": err_msg}), status_code
    return jsonify({"success": True, "session": session.to_dict()}), 200


@app.route("/api/call/session/<session_id>/answer", methods=["POST"])
def submit_call_answer(session_id):
    """Submit WebRTC SDP answer."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON payload"}), 400
    answer = data.get("answer")
    role = data.get("role", "patient")
    if not answer:
        return jsonify({"error": "Missing 'answer' in request body"}), 400
    success, err_msg, session = call_session_manager.set_answer(session_id, answer=answer, role=role)
    if not success:
        status_code = 404 if err_msg == "Session not found" else 400
        return jsonify({"error": err_msg}), status_code
    return jsonify({"success": True, "session": session.to_dict()}), 200


@app.route("/api/call/session/<session_id>/ice", methods=["POST"])
def submit_call_ice(session_id):
    """Submit ICE candidate."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON payload"}), 400
    candidate = data.get("candidate")
    role = data.get("role")
    if not role:
        return jsonify({"error": "Missing 'role' (caregiver or patient)"}), 400
    if candidate is None:
        return jsonify({"error": "Missing 'candidate' object"}), 400
    success, err_msg, count = call_session_manager.add_ice_candidate(session_id, candidate=candidate, role=role)
    if not success:
        status_code = 404 if err_msg == "Session not found" else 400
        return jsonify({"error": err_msg}), status_code
    return jsonify({"success": True, "count": count}), 200


@app.route("/api/call/session/<session_id>/end", methods=["POST"])
def end_call_session(session_id):
    """End an active call session."""
    data = request.get_json(silent=True) or {}
    ended_by = data.get("role", "user")
    success, err_msg, session = call_session_manager.end_session(session_id, ended_by=ended_by)
    if not success:
        return jsonify({"error": err_msg}), 404
    return jsonify({"success": True, "session": session.to_dict()}), 200


# ==============================================================================
# STATIC FRONTEND SERVING (PERSON A & CAREGIVER DASHBOARD)
# ==============================================================================

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
CAREGIVER_DIR = os.path.join(PROJECT_ROOT, "caregiver")


@app.route("/")
def serve_index():
    """Serve Person A's Button Phone Simulator."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/frontend/<path:filename>")
def serve_frontend_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/<path:filename>")
def serve_root_fallback(filename):
    """Fallback handler for root-relative static assets like style.css or script.js."""
    if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
        return send_from_directory(FRONTEND_DIR, filename)
    elif os.path.exists(os.path.join(CAREGIVER_DIR, filename)):
        return send_from_directory(CAREGIVER_DIR, filename)
    return jsonify({"error": "File not found"}), 404


@app.route("/caregiver")
def serve_caregiver_index():
    """Serve Caregiver Monitoring Dashboard."""
    return send_from_directory(CAREGIVER_DIR, "caregiver.html")


@app.route("/caregiver/<path:filename>")
def serve_caregiver_static(filename):
    return send_from_directory(CAREGIVER_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    use_https = os.environ.get("SHECODES_HTTPS", "").lower() in {"1", "true", "yes"}
    scheme = "https" if use_https else "http"
    print(f"Starting SHECODES Dementia Companion Backend on {scheme}://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        use_reloader=not use_https,
        ssl_context="adhoc" if use_https else None,
    )
