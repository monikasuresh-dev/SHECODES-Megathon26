# SHECODES Dementia Companion
### AI-Agent-Powered Persistent Health Memory Layer & Deterministic Conversational Intelligence for Elderly Patients

> **Core Architectural Principle:**
> *"The LLM generates the conversation; the deterministic intelligence layer controls repetition, distress, risk, and escalation."*
>
> **Safety & Ethics Boundary:**
> This system is an assistive interaction prototype and caregiver-support telemetry layer. It **does NOT** diagnose dementia, clinical depression, or predict medical emergencies.

---

## 1. System Architecture

```text
                     FRONTEND (Person A)
                             │
                             │ POST /chat
                             ▼
                      ┌──────────────┐
                      │   Flask API  │
                      │  (Person B)  │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │Privacy Filter│
                      │  (Person D)  │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │Patient Memory│
                      │ patient.json │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │Prompt Builder│
                      │  prompt.py   │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │ LLM / Static │
                      │   Response   │
                      └──────┬───────┘
                             │
                             ▼
                   ┌───────────────────┐
                   │PERSON C INTEL     │
                   │- Repetition (10x) │
                   │- Distress (0-100) │
                   │- Risk (G/Y/R)     │
                   │- Escalation       │
                   └─────────┬─────────┘
                             │
                             ▼
                     Structured Result
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
    Frontend / Phone UI             Caregiver Dashboard
 (Captions, Voice TTS, Alert)      (Telemetry, Alert Ack)
```

---

## 2. Team Division of Responsibilities

| Role | Member | Responsibilities | Key Files |
| :--- | :--- | :--- | :--- |
| **Frontend** | Person A | Button phone UI, green talk button, mic, captions, TTS, caregiver alert banner | `frontend/index.html`<br>`frontend/style.css`<br>`frontend/script.js` |
| **Backend** | Person B | Flask application, `/chat` endpoint, patient JSON memory, prompt builder, LLM integration, offline fallback | `backend/app.py`<br>`backend/patient.json`<br>`backend/prompt.py`<br>`backend/static_responses.py` |
| **Intelligence** | Person C | Deterministic repetition tracking, distress scoring, GREEN/YELLOW/RED classification, escalation triggers | `backend/repetition.py`<br>`backend/distress.py`<br>`backend/escalation.py`<br>`backend/intelligence.py` |
| **Safety & Testing** | Person D | PII redaction, safety guardrails, delusion validation approach, automated scenario test suite | `backend/privacy.py`<br>`tests/test_scenarios.py`<br>`tests/test_intelligence.py` |

---

## 3. Directory Layout

```text
SHECODES-Dementia-Companion/
│
├── frontend/                     # Person A: Button Phone Simulator
│   ├── index.html                # Accessible high-contrast phone UI
│   ├── style.css                 # Tactile buttons & warm comforting theme
│   └── script.js                 # Web Speech API & TTS audio handler
│
├── backend/                      # Person B & Person C Integration
│   ├── __init__.py
│   ├── app.py                    # Flask API server & static file host
│   ├── patient.json              # Persistent health memory & comfort anchors
│   ├── prompt.py                 # Grounded dementia system prompts
│   ├── privacy.py                # Person D: PII masking & safety filter
│   ├── repetition.py             # Person C: Deterministic repetition tracker
│   ├── distress.py               # Person C: Explainable distress scoring (0-100)
│   ├── escalation.py             # Risk classification & caregiver alerts
│   ├── intelligence.py           # Person C: Unified Intelligence Engine
│   └── static_responses.py       # Offline grounded fallback generator
│
├── caregiver/                    # Caregiver Monitoring Portal
│   ├── caregiver.html            # Real-time telemetry dashboard
│   ├── caregiver.css             # Risk status badges & alert feed styling
│   └── caregiver.js              # Live telemetry polling & alert acknowledgement
│
├── tests/                        # Automated Test Suites
│   ├── __init__.py
│   ├── test_intelligence.py      # Person C intelligence unit tests (23 tests)
│   └── test_scenarios.py         # End-to-end integration scenario tests (8 tests)
│
├── .env                          # Configuration (PORT, optional GEMINI_API_KEY)
├── .gitignore
├── requirements.txt              # Lightweight dependencies
└── README.md
```

---

## 4. Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Dependencies are purely standard `Flask`, `flask-cors`, and `python-dotenv`. The application is completely functional **offline** with zero external API keys required).*

### 2. (Optional) Configure Gemini API
If you wish to use Google Gemini 2.5 Flash for live dynamic cloud generation, edit `.env`:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```
If left blank, the app seamlessly uses the **patient-grounded offline response engine**, referencing Eleanor's daughter Sarah, Barnaby the dog, and courtyard yellow roses.

### 3. Start the Server
```bash
python backend/app.py
```
Open your browser:
- **Button Phone Interface (Person A)**: [http://localhost:5000/](http://localhost:5000/)
- **Caregiver Dashboard**: [http://localhost:5000/caregiver](http://localhost:5000/caregiver)
- **API Health Check**: [http://localhost:5000/api/health](http://localhost:5000/api/health)

---

## 5. API Contracts

### `POST /chat`
**Request Payload:**
```json
{
  "message": "Where is my daughter?",
  "history": [
    "Good morning.",
    "Good morning Eleanor! How are you feeling today?"
  ]
}
```

**Response Payload:**
```json
{
  "reply": "Sarah loves you dearly, Eleanor. She will be here to see you this evening around 5:00 PM. Barnaby is doing wonderfully too.",
  "intelligence": {
    "risk_level": "YELLOW",
    "distress_score": 0,
    "distress_level": "LOW",
    "repetition_count": 2,
    "repetition_level": "MEDIUM",
    "repeated_topic": "daughter",
    "escalate": false,
    "reason": "Repeated concern detected regarding 'daughter'",
    "signals": [
      "repeated_question"
    ]
  },
  "privacy": {
    "pii_detected": false,
    "redactions": [],
    "safety_warning": null
  },
  "patient": {
    "name": "Eleanor",
    "room": "Suite 14"
  }
}
```

---

## 6. Running Tests

### Run Person C Unit Tests:
```bash
python -m unittest tests/test_intelligence.py -v
```

### Run End-to-End Scenario Tests:
```bash
python -m unittest tests/test_scenarios.py -v
```

### Run All Tests:
```bash
python -m unittest discover -s tests -v
```
*(All 31 test cases pass cleanly).*
