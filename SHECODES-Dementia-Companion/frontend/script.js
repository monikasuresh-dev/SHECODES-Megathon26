/* =========================================================
   DIGITAL BUTTON PHONE SIMULATOR — script.js
   Voice-Only Real-Time Conversational AI Companion
   -----------------------------------------------------------
   EXPLICIT FRONTEND STATE MACHINE:
     - IDLE       : Phone is on hook / ready. No mic, no TTS.
     - LISTENING  : Green call active. Mic continuously listening.
     - PROCESSING : Patient utterance debounced -> sending to POST /chat.
                    Mic is fully stopped/aborted.
     - SPEAKING   : AI companion speaks aloud via SpeechSynthesis (TTS).
                    Mic is strictly disabled to prevent audio feedback.
     - TAKEOVER   : Caregiver has taken over session. AI mic & TTS
                    are permanently silenced for the call duration.
========================================================= */

/* ---------------------------------------------------------
   1. STATE MACHINE ENUM & CONTROLLER
--------------------------------------------------------- */
const STATE = {
  IDLE: "IDLE",
  LISTENING: "LISTENING",
  PROCESSING: "PROCESSING",
  SPEAKING: "SPEAKING",
  TAKEOVER: "TAKEOVER",
};

let currentState = STATE.IDLE;

// Recognition lifecycle guards
let isRecognitionRunning = false;
let isRecognitionStarting = false;
let recognitionInstance = null;

// Speech accumulation & timers
let accumulatedTranscript = "";
let silenceTimer = null;
let restartTimer = null;
let ttsWatchdogTimer = null;
let ttsCooldownTimer = null;

const SILENCE_TIMEOUT_MS = 1500; // 1.5s natural pause before sending speech
const conversationHistory = [];  // Kept in internal session, not shown on LCD
const patientId = "PATIENT-84920";
const HEARTBEAT_INTERVAL_MS = 5000;

async function sendPatientHeartbeat() {
  try {
    const response = await fetch("/api/patient/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId }),
      keepalive: true,
    });
    if (!response.ok) throw new Error(`Heartbeat HTTP ${response.status}`);
    if (phoneConnection) {
      phoneConnection.textContent = "ONLINE";
      phoneConnection.classList.add("online");
    }
    console.log("[PATIENT] Connected to shared backend");
  } catch (error) {
    if (phoneConnection) {
      phoneConnection.textContent = "OFFLINE";
      phoneConnection.classList.remove("online");
    }
    console.warn("[PATIENT] Connection error:", error);
  }
}

sendPatientHeartbeat();
setInterval(sendPatientHeartbeat, HEARTBEAT_INTERVAL_MS);
window.addEventListener("online", sendPatientHeartbeat);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) sendPatientHeartbeat();
});

// DOM References
const displayText = document.getElementById("displayText");
const charCount = document.getElementById("charCount");
const clockEl = document.getElementById("clock");
const keypad = document.getElementById("keypad");
const clearBtn = document.getElementById("clearBtn");
const callBtn = document.getElementById("callBtn");
const endBtn = document.getElementById("endBtn");
const phoneConnection = document.getElementById("phoneConnection");

/**
 * Updates the classic phone LCD display with short status text.
 * Strictly prevents full conversational messages from displaying.
 */
function setLcdStatus(statusText, footerStatus) {
  if (displayText) {
    displayText.textContent = statusText;
  }
  if (charCount) {
    charCount.textContent = footerStatus || statusText;
  }
}

/**
 * Clear all pending asynchronous timers across state transitions.
 */
function clearAllTimers() {
  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
  if (ttsWatchdogTimer) {
    clearTimeout(ttsWatchdogTimer);
    ttsWatchdogTimer = null;
  }
  if (ttsCooldownTimer) {
    clearTimeout(ttsCooldownTimer);
    ttsCooldownTimer = null;
  }
}

/**
 * Explicit state machine transition router.
 */
function transitionTo(newState, data = {}) {
  console.log(`[State] ${currentState} -> ${newState}`, data);
  clearAllTimers();
  currentState = newState;

  switch (newState) {
    case STATE.IDLE:
      stopOrAbortRecognition(true);
      cancelSpeechSynthesis();
      setLcdStatus("READY", "READY");
      if (callBtn) callBtn.classList.remove("listening");
      accumulatedTranscript = "";
      break;

    case STATE.LISTENING:
      cancelSpeechSynthesis();
      setLcdStatus("LISTENING...", "ACTIVE");
      if (callBtn) callBtn.classList.add("listening");
      accumulatedTranscript = "";
      safeStartRecognition();
      break;

    case STATE.PROCESSING:
      stopOrAbortRecognition(true);
      if (callBtn) callBtn.classList.remove("listening");
      setLcdStatus("PROCESSING...", "WAIT");
      break;

    case STATE.SPEAKING:
      // Completely shutdown microphone while speaking to prevent feedback loops
      stopOrAbortRecognition(true);
      if (callBtn) callBtn.classList.remove("listening");
      setLcdStatus("AI SPEAKING...", "SPEAKING");
      break;

    case STATE.TAKEOVER:
      stopOrAbortRecognition(true);
      cancelSpeechSynthesis();
      if (callBtn) callBtn.classList.remove("listening");
      setLcdStatus("CAREGIVER CALL", "LIVE");
      break;
  }
}

/* ---------------------------------------------------------
   2. SOUND ENGINE (Web Audio API - DTMF Tones)
--------------------------------------------------------- */
let audioCtx = null;

const DTMF_FREQUENCIES = {
  "1": [697, 1209], "2": [697, 1336], "3": [697, 1477],
  "4": [770, 1209], "5": [770, 1336], "6": [770, 1477],
  "7": [852, 1209], "8": [852, 1336], "9": [852, 1477],
  "*": [941, 1209], "0": [941, 1336], "#": [941, 1477],
};

function ensureAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

function playTone(key) {
  try {
    const ctx = ensureAudioContext();
    const [freq1, freq2] = DTMF_FREQUENCIES[key] || [440, 480];

    const now = ctx.currentTime;
    const duration = 0.09;

    const gainNode = ctx.createGain();
    gainNode.gain.setValueAtTime(0.15, now);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    gainNode.connect(ctx.destination);

    [freq1, freq2].forEach((freq) => {
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = freq;
      osc.connect(gainNode);
      osc.start(now);
      osc.stop(now + duration);
    });
  } catch (e) {
    console.warn("AudioContext tone notice:", e);
  }
}

/* ---------------------------------------------------------
   3. SPEECH-TO-TEXT ENGINE (Web Speech API)
--------------------------------------------------------- */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

/**
 * Creates and binds a fresh SpeechRecognition instance.
 * Fresh instances guarantee no stale internal buffer accumulation across turns.
 */
function createRecognitionInstance() {
  if (!SpeechRecognition) return null;

  const rec = new SpeechRecognition();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = "en-IN"; // Preserved as required

  rec.onstart = () => {
    console.log("[STT] onstart event fired.");
    isRecognitionRunning = true;
    isRecognitionStarting = false;

    if (currentState === STATE.LISTENING) {
      setLcdStatus("LISTENING...", "ACTIVE");
      if (callBtn) callBtn.classList.add("listening");
    } else {
      console.log(`[STT] onstart arrived in state ${currentState}, aborting.`);
      try { rec.abort(); } catch (e) {}
    }
  };

  rec.onresult = (event) => {
    // Strictly discard any audio if not actively in LISTENING state
    if (currentState !== STATE.LISTENING) return;

    let interimChunk = "";
    let finalChunk = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const result = event.results[i];
      const text = result[0].transcript;
      if (result.isFinal) {
        finalChunk += " " + text;
      } else {
        interimChunk += text;
      }
    }

    if (finalChunk.trim()) {
      accumulatedTranscript += " " + finalChunk.trim();
      accumulatedTranscript = accumulatedTranscript.trim();
    }

    const currentSpeech = (accumulatedTranscript + " " + interimChunk).trim();

    if (currentSpeech.length > 0) {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
      }

      silenceTimer = setTimeout(() => {
        const textToSend = (accumulatedTranscript.trim() || currentSpeech.trim()).trim();
        accumulatedTranscript = "";

        if (textToSend.length > 0 && currentState === STATE.LISTENING) {
          handlePatientSpeech(textToSend);
        }
      }, SILENCE_TIMEOUT_MS);
    }
  };

  rec.onerror = (event) => {
    console.warn("[STT] onerror event:", event.error);
    isRecognitionStarting = false;

    switch (event.error) {
      case "not-allowed":
      case "service-not-allowed":
        setLcdStatus("MIC BLOCKED", "PERMISSION");
        isRecognitionRunning = false;
        transitionTo(STATE.IDLE);
        break;

      case "network":
        setLcdStatus("VOICE NET ERR", "ERROR");
        if (currentState === STATE.LISTENING) {
          scheduleSafeRestart(1200);
        }
        break;

      case "audio-capture":
        setLcdStatus("MIC HARDWARE ERR", "ERROR");
        transitionTo(STATE.IDLE);
        break;

      case "no-speech":
        // Quiet pause in continuous mode — let onend safely restart if still listening
        break;

      case "aborted":
        // Intentional abort from state change
        break;

      default:
        console.warn("[STT] Unhandled error:", event.error);
        break;
    }
  };

  rec.onend = () => {
    console.log("[STT] onend event fired.");
    isRecognitionRunning = false;
    isRecognitionStarting = false;

    // ONLY restart if still in LISTENING state
    // NEVER restart while in PROCESSING, SPEAKING, TAKEOVER, or IDLE
    if (currentState === STATE.LISTENING) {
      scheduleSafeRestart(250);
    }
  };

  return rec;
}

/**
 * Cleanly stops or aborts recognition and detaches old listeners
 * to prevent zombie events from restarting speech recognition.
 */
function stopOrAbortRecognition(abort = false) {
  if (recognitionInstance) {
    try {
      recognitionInstance.onend = null;
      recognitionInstance.onerror = null;
      recognitionInstance.onresult = null;
      recognitionInstance.onstart = null;
      if (abort) {
        recognitionInstance.abort();
      } else {
        recognitionInstance.stop();
      }
    } catch (e) {
      // Ignore if already stopped
    }
    recognitionInstance = null;
  }
  isRecognitionRunning = false;
  isRecognitionStarting = false;
}

/**
 * Safely starts speech recognition with state and duplicate-start guards.
 */
function safeStartRecognition() {
  if (currentState !== STATE.LISTENING) {
    console.log(`[STT] SafeStart suppressed: state is ${currentState}`);
    return;
  }

  if (!SpeechRecognition) {
    setLcdStatus("MIC NOT SUPPORTED", "UNSUPPORTED");
    return;
  }

  if (isRecognitionRunning || isRecognitionStarting) {
    console.log("[STT] Recognition already active or starting.");
    return;
  }

  isRecognitionStarting = true;

  if (!recognitionInstance) {
    recognitionInstance = createRecognitionInstance();
  }

  try {
    recognitionInstance.start();
  } catch (err) {
    isRecognitionStarting = false;
    if (err.name === "InvalidStateError" || (err.message && err.message.includes("already started"))) {
      console.warn("[STT] Caught InvalidStateError: marking running.");
      isRecognitionRunning = true;
    } else {
      console.error("[STT] Start exception:", err);
      if (currentState === STATE.LISTENING) {
        scheduleSafeRestart(400);
      }
    }
  }
}

/**
 * Schedule restart with guard validation before execution.
 */
function scheduleSafeRestart(delayMs = 250) {
  if (restartTimer) clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    if (currentState === STATE.LISTENING && !isRecognitionRunning && !isRecognitionStarting) {
      safeStartRecognition();
    }
  }, delayMs);
}

/* ---------------------------------------------------------
   4. TEXT-TO-SPEECH (Browser SpeechSynthesis - AUDIO ONLY)
--------------------------------------------------------- */
function cancelSpeechSynthesis() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function speakAiResponse(replyText) {
  if (!("speechSynthesis" in window)) {
    console.warn("[TTS] speechSynthesis not supported.");
    setTimeout(() => {
      if (currentState === STATE.SPEAKING) {
        transitionTo(STATE.LISTENING);
      }
    }, 2500);
    return;
  }

  cancelSpeechSynthesis();

  const utterance = new SpeechSynthesisUtterance(replyText);
  utterance.rate = 0.9;
  utterance.pitch = 1.0;
  utterance.volume = 1.0;
  utterance.lang = "en-IN";

  let hasEnded = false;

  const onComplete = () => {
    if (hasEnded) return;
    hasEnded = true;

    if (ttsWatchdogTimer) {
      clearTimeout(ttsWatchdogTimer);
      ttsWatchdogTimer = null;
    }

    console.log("[TTS] Finished speaking AI response.");

    // Return to LISTENING only if still in SPEAKING state
    if (currentState === STATE.SPEAKING) {
      // 300ms cooldown to ensure speaker room audio dissipates before mic opens
      ttsCooldownTimer = setTimeout(() => {
        if (currentState === STATE.SPEAKING) {
          transitionTo(STATE.LISTENING);
        }
      }, 300);
    }
  };

  utterance.onend = onComplete;
  utterance.onerror = (e) => {
    console.warn("[TTS] Utterance error:", e);
    onComplete();
  };

  // Watchdog timer: prevents speech synthesis hanging indefinitely on mobile browsers
  const wordCount = (replyText || "").split(/\s+/).length;
  const timeoutMs = Math.max(4000, (wordCount / 2.0) * 1000 + 4000);
  ttsWatchdogTimer = setTimeout(() => {
    if (!hasEnded && currentState === STATE.SPEAKING) {
      console.warn("[TTS] Watchdog expired; forcing completion.");
      cancelSpeechSynthesis();
      onComplete();
    }
  }, timeoutMs);

  window.speechSynthesis.speak(utterance);
}

/* ---------------------------------------------------------
   5. BACKEND /chat INTEGRATION
--------------------------------------------------------- */
async function handlePatientSpeech(spokenText) {
  if (!spokenText || !spokenText.trim()) return;

  transitionTo(STATE.PROCESSING);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: spokenText.trim(),
        history: conversationHistory,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    const reply = data.reply || "I am right here with you, Lakshmi. You are safe.";

    conversationHistory.push(spokenText.trim());

    // Abort if state changed while waiting for fetch
    if (currentState !== STATE.PROCESSING) {
      console.log(`[Chat] State moved to ${currentState} during fetch. Dropping TTS.`);
      return;
    }

    transitionTo(STATE.SPEAKING);
    if (data.intelligence && (data.intelligence.risk_level === "RED" || data.intelligence.escalate)) {
      setLcdStatus("HELP ON THE WAY", "ALERTED");
    }
    speakAiResponse(reply);

  } catch (err) {
    console.error("[Chat] Request failed:", err);
    if (currentState === STATE.PROCESSING) {
      setLcdStatus("CONNECTION ERROR", "ERROR");
      transitionTo(STATE.SPEAKING);
      speakAiResponse("I am having trouble connecting. Take a calm breath, I am right here with you.");
    }
  }
}

/* ---------------------------------------------------------
   6. GREEN CALL / TALK BUTTON
--------------------------------------------------------- */
function startCall() {
  playTone("1"); // Connection chime

  if (!window.isSecureContext) {
    setLcdStatus("OPEN HTTPS", "MIC NEEDS HTTPS");
    console.warn("[STT] Mobile microphone access requires an HTTPS origin.");
    return;
  }

  if (!SpeechRecognition) {
    setLcdStatus("MIC NOT SUPPORTED", "UNSUPPORTED");
    return;
  }

  // If already active or in another active state, ignore redundant call button taps
  if (currentState !== STATE.IDLE) {
    console.log(`[Call] Call button tapped in state ${currentState}, ignoring.`);
    return;
  }

  transitionTo(STATE.LISTENING);
}

/* ---------------------------------------------------------
   7. RED END CALL BUTTON
--------------------------------------------------------- */
function endCall() {
  playTone("*"); // Hang up tone

  if (patientWebRtcActiveSessionId) {
    fetch(`/api/call/session/${patientWebRtcActiveSessionId}/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "patient" }),
    }).catch(() => {});
  }
  teardownPatientWebRtc();

  transitionTo(STATE.IDLE);
  setLcdStatus("CALL ENDED", "OFFLINE");

  setTimeout(() => {
    if (currentState === STATE.IDLE) {
      setLcdStatus("READY", "READY");
    }
  }, 2500);
}

/* ---------------------------------------------------------
   8. PHYSICAL KEYPAD & EVENT WIRING
--------------------------------------------------------- */
function pressKey(value) {
  playTone(value);

  // If idle, show typed digit on LCD
  if (currentState === STATE.IDLE) {
    if (displayText && (displayText.textContent === "READY" || displayText.textContent === "CALL ENDED")) {
      displayText.textContent = value;
      charCount.textContent = "DIALING";
    } else if (displayText && displayText.textContent.length < 12) {
      displayText.textContent += value;
    }
  }
}

function clearScreen() {
  playTone();
  if (currentState === STATE.IDLE) {
    setLcdStatus("READY", "READY");
  }
}

// Wire Keypad
keypad.addEventListener("pointerdown", (event) => {
  const keyEl = event.target.closest(".key");
  if (!keyEl) return;

  event.preventDefault();
  const value = keyEl.dataset.key;
  keyEl.classList.add("active");
  pressKey(value);
});

["pointerup", "pointercancel", "pointerleave"].forEach((evtName) => {
  keypad.addEventListener(evtName, (event) => {
    const keyEl = event.target.closest(".key");
    if (keyEl) keyEl.classList.remove("active");
  });
});

clearBtn.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  clearScreen();
});

callBtn.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  startCall();
});

endBtn.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  endCall();
});

/* ---------------------------------------------------------
   9. CLOCK (Cosmetic Status Bar)
--------------------------------------------------------- */
function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, "0");
  const minutes = String(now.getMinutes()).padStart(2, "0");
  if (clockEl) clockEl.textContent = `${hours}:${minutes}`;
}
updateClock();
setInterval(updateClock, 1000 * 30);

/* ---------------------------------------------------------
   10. WEBRTC LIVE INTERCOM INTEGRATION (PATIENT SIDE)
--------------------------------------------------------- */
const remoteAudioEl = document.getElementById("remoteAudio");

let patientPeerConnection = null;
let patientLocalMediaStream = null;
let patientWebRtcActiveSessionId = null;
let patientProcessedCaregiverIceIndex = 0;
let patientSignalingPollInterval = null;
let isHandlingCall = false;

async function checkForActiveCaregiverSession() {
  // If already engaged in live caregiver call, skip polling
  if (isHandlingCall || currentState === STATE.TAKEOVER) return;

  try {
    const res = await fetch("/api/call/session/active");
    if (!res.ok) return;
    const data = await res.json();
    const session = data.session;

    if (
      session &&
      session.status !== "ENDED" &&
      session.has_offer &&
      session.offer &&
      session.caregiver_joined &&
      session.session_id !== patientWebRtcActiveSessionId
    ) {
      console.log("[WebRTC Patient] Active caregiver offer detected:", session.session_id);
      handleIncomingCaregiverCall(session);
    }
  } catch (err) {
    // Normal poll retry on network pause
  }
}

async function handleIncomingCaregiverCall(session) {
  if (isHandlingCall) return;
  isHandlingCall = true;
  patientWebRtcActiveSessionId = session.session_id;

  // 1. Transition to TAKEOVER immediately:
  // - stops SpeechRecognition
  // - cancels SpeechSynthesis
  // - clears STT timers
  // - prevents STT restart
  // - prevents new /chat requests
  transitionTo(STATE.TAKEOVER);
  setLcdStatus("CONNECTING...", "CAREGIVER");

  try {
    // 2. Join session as patient
    await fetch(`/api/call/session/${session.session_id}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "patient" }),
    });

    // 3. Request patient microphone
    try {
      patientLocalMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      console.error("[WebRTC Patient] Mic access denied:", e);
      setLcdStatus("MIC BLOCKED", "ERROR");
      teardownPatientWebRtc();
      setTimeout(() => {
        if (currentState === STATE.TAKEOVER) transitionTo(STATE.IDLE);
      }, 3000);
      return;
    }

    // 4. Create RTCPeerConnection with STUN
    patientPeerConnection = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    patientProcessedCaregiverIceIndex = 0;

    // Add local microphone audio track
    patientLocalMediaStream.getTracks().forEach((track) => {
      patientPeerConnection.addTrack(track, patientLocalMediaStream);
    });

    // Route caregiver audio to phone speaker
    patientPeerConnection.ontrack = (event) => {
      console.log("[WebRTC Patient] Received caregiver audio track.");
      if (remoteAudioEl && event.streams[0]) {
        remoteAudioEl.srcObject = event.streams[0];
        remoteAudioEl.play().catch((e) => console.warn("Remote audio play notice:", e));
      }
    };

    // Candidate handling
    patientPeerConnection.onicecandidate = (event) => {
      if (event.candidate && patientWebRtcActiveSessionId) {
        sendPatientIce(patientWebRtcActiveSessionId, event.candidate);
      }
    };

    patientPeerConnection.onconnectionstatechange = () => {
      const state = patientPeerConnection ? patientPeerConnection.connectionState : "closed";
      console.log("[WebRTC Patient] Connection state:", state);
      if (state === "connected") {
        setLcdStatus("CAREGIVER CONNECTED", "LIVE");
      } else if (state === "failed") {
        setLcdStatus("CALL FAILED", "ERROR");
        teardownPatientWebRtc();
        setTimeout(() => {
          if (currentState === STATE.TAKEOVER) transitionTo(STATE.IDLE);
        }, 3000);
      } else if (state === "closed" || state === "disconnected") {
        setLcdStatus("CALL ENDED", "OFFLINE");
        teardownPatientWebRtc();
        setTimeout(() => {
          if (currentState === STATE.TAKEOVER) transitionTo(STATE.IDLE);
        }, 2500);
      }
    };

    // 5. Set remote description from offer
    await patientPeerConnection.setRemoteDescription(new RTCSessionDescription(session.offer));

    // 6. Create answer
    const answer = await patientPeerConnection.createAnswer();
    await patientPeerConnection.setLocalDescription(answer);

    // 7. Send answer to signaling
    await fetch(`/api/call/session/${session.session_id}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer: patientPeerConnection.localDescription, role: "patient" }),
    });

    // 8. Start polling for caregiver ICE candidates and session termination
    startPatientSignalingPoll(session.session_id);

  } catch (err) {
    console.error("[WebRTC Patient] Live session setup failed:", err);
    setLcdStatus("CALL FAILED", "ERROR");
    teardownPatientWebRtc();
    setTimeout(() => {
      if (currentState === STATE.TAKEOVER) transitionTo(STATE.IDLE);
    }, 3000);
  }
}

function startPatientSignalingPoll(sessionId) {
  if (patientSignalingPollInterval) clearInterval(patientSignalingPollInterval);

  patientSignalingPollInterval = setInterval(async () => {
    if (!sessionId || !patientPeerConnection) return;

    try {
      const res = await fetch(`/api/call/session/${sessionId}`);
      if (!res.ok) return;
      const session = await res.json();

      if (session.status === "ENDED") {
        console.log("[WebRTC Patient] Session ended by caregiver.");
        setLcdStatus("CALL ENDED", "OFFLINE");
        teardownPatientWebRtc();
        setTimeout(() => {
          if (currentState === STATE.TAKEOVER) transitionTo(STATE.IDLE);
        }, 2500);
        return;
      }

      // Add newly arrived caregiver ICE candidates
      const candidates = session.caregiver_ice_candidates || [];
      while (patientProcessedCaregiverIceIndex < candidates.length) {
        const cand = candidates[patientProcessedCaregiverIceIndex];
        if (patientPeerConnection && patientPeerConnection.remoteDescription) {
          patientPeerConnection.addIceCandidate(new RTCIceCandidate(cand)).catch((e) => console.warn(e));
        }
        patientProcessedCaregiverIceIndex++;
      }
    } catch (e) {
      console.warn("[WebRTC Patient] Polling notice:", e);
    }
  }, 800);
}

async function sendPatientIce(sessionId, candidate) {
  try {
    await fetch(`/api/call/session/${sessionId}/ice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate: candidate.toJSON ? candidate.toJSON() : candidate, role: "patient" }),
    });
  } catch (e) {
    console.warn("Failed to send patient ICE:", e);
  }
}

function teardownPatientWebRtc() {
  isHandlingCall = false;

  if (patientSignalingPollInterval) {
    clearInterval(patientSignalingPollInterval);
    patientSignalingPollInterval = null;
  }

  if (patientLocalMediaStream) {
    patientLocalMediaStream.getTracks().forEach((t) => t.stop());
    patientLocalMediaStream = null;
  }

  if (patientPeerConnection) {
    patientPeerConnection.close();
    patientPeerConnection = null;
  }

  if (remoteAudioEl) {
    remoteAudioEl.srcObject = null;
  }

  patientWebRtcActiveSessionId = null;
  patientProcessedCaregiverIceIndex = 0;
}

// Poll for caregiver call requests every 1.5s
setInterval(checkForActiveCaregiverSession, 1500);

/* ---------------------------------------------------------
   11. DEBUGGING & STATE MACHINE INSPECTION HOOK
--------------------------------------------------------- */
window.__COMPANION_STATE__ = {
  STATE,
  getState: () => currentState,
  triggerTakeover: () => transitionTo(STATE.TAKEOVER),
  resetToIdle: () => transitionTo(STATE.IDLE),
  getCallSessionId: () => patientWebRtcActiveSessionId,
};
