/**
 * SHECODES Dementia Companion - Caregiver Dashboard Controller
 * Multi-view navigation, real-time telemetry polling, patient profile hydration,
 * live alert escalation management, and system diagnostics.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Navigation & Tab Elements
  const navItems = document.querySelectorAll(".nav-item");
  const tabViews = document.querySelectorAll(".tab-view");
  const pageTitle = document.getElementById("page-title");
  const pageSubtitle = document.getElementById("page-subtitle");
  const mobileToggle = document.getElementById("mobile-toggle");
  const sidebar = document.getElementById("sidebar");
  const jumpToAlertsBtn = document.getElementById("jump-to-alerts-btn");

  // Dashboard Telemetry Elements
  const riskPill = document.getElementById("risk-pill");
  const riskExplanation = document.getElementById("risk-explanation");
  const distressScoreNum = document.getElementById("distress-score-num");
  const distressBar = document.getElementById("distress-bar");
  const activeSignalsContainer = document.getElementById("active-signals-container");
  const repetitionCountNum = document.getElementById("repetition-count-num");
  const repetitionLevelBadge = document.getElementById("repetition-level-badge");
  const repetitionTopicVal = document.getElementById("repetition-topic-val");
  const alertsCount = document.getElementById("alerts-count");
  const alertsCountBadge = document.getElementById("alerts-count-badge");
  const alertSub = document.getElementById("alert-sub");
  const alertsBadgeText = document.getElementById("alerts-badge-text");
  const sbAlertsBadge = document.getElementById("sb-alerts-badge");
  const alertsContainer = document.getElementById("alerts-container");
  const timelineContainer = document.getElementById("timeline-container");
  const refreshTime = document.getElementById("refresh-time");
  const lastInteractionTime = document.getElementById("last-interaction-time");
  const overallResidentState = document.getElementById("overall-resident-state");
  const residentSessionBadge = document.getElementById("resident-session-badge");
  const patientConnectionStatus = document.getElementById("patient-connection-status");

  // Alerts Page Elements
  const alertsPageActiveCount = document.getElementById("alerts-page-active-count");
  const alertsPageMonitoredCount = document.getElementById("alerts-page-monitored-count");
  const alertsPageAckCount = document.getElementById("alerts-page-ack-count");
  const alertsFeedList = document.getElementById("alerts-feed-list");
  const filterPills = document.querySelectorAll(".filter-pill");

  // Diagnostic Elements
  const diagBackendStatus = document.getElementById("diag-backend-status");
  const diagGeminiStatus = document.getElementById("diag-gemini-status");

  // State
  let currentFilter = "all";
  let storedAlertsCache = [];
  let acknowledgedAlertsStore = new Set();
  let latestActiveCallSession = null;

  // Tab Definitions metadata
  const tabMeta = {
    dashboard: {
      title: "Caregiver Dashboard",
      subtitle: "Real-time interaction risk signals & persistent health memory"
    },
    patient: {
      title: "Resident Profile & Care Guidelines",
      subtitle: "Comprehensive patient health memory, family contacts & grounding anchors"
    },
    memories: {
      title: "Persistent Health Memories",
      subtitle: "Categorized life history, familiar places, and daily grounding routines"
    },
    alerts: {
      title: "Care Escalations & Alerts",
      subtitle: "Deterministic distress signals, repetition tracking & recommended actions"
    },
    settings: {
      title: "Caregiver & Telemetry Settings",
      subtitle: "Notification preferences, monitoring thresholds, and live system diagnostics"
    }
  };

  // ==========================================================================
  // TAB NAVIGATION
  // ==========================================================================
  function switchTab(tabName) {
    navItems.forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
    });

    tabViews.forEach(view => {
      view.classList.toggle("active", view.id === `view-${tabName}`);
    });

    if (tabMeta[tabName]) {
      pageTitle.textContent = tabMeta[tabName].title;
      pageSubtitle.textContent = tabMeta[tabName].subtitle;
    }

    if (window.innerWidth <= 900 && sidebar) {
      sidebar.classList.remove("open");
    }
  }

  navItems.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabName = btn.getAttribute("data-tab");
      if (tabName) switchTab(tabName);
    });
  });

  if (jumpToAlertsBtn) {
    jumpToAlertsBtn.addEventListener("click", () => switchTab("alerts"));
  }

  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // ==========================================================================
  // PATIENT PROFILE HYDRATION (/api/patient)
  // ==========================================================================
  async function hydratePatientProfile() {
    try {
      const response = await fetch("/api/patient");
      if (!response.ok) return;
      const p = await response.json();

      // Top / Sidebar
      setText("patient-full-name", p.name || "Lakshmi Narayanan");
      setText("prof-full-name", p.name || "Lakshmi Narayanan");
      setText("sb-patient-name", p.name || "Lakshmi Narayanan");
      setText("patient-room", p.room_number || "Anna Nagar, Chennai");
      setText("prof-room", p.room_number || "Anna Nagar, Chennai");
      setText("sb-patient-room", p.room_number || "Anna Nagar, Chennai");
      setText("patient-condition", p.condition || "Mild Dementia");
      setText("prof-condition", p.condition || "Mild-to-Moderate Dementia");
      setText("prof-patient-id", p.patient_id || "PATIENT-84920");
      setText("prof-age", p.age ? `${p.age}` : "72");
      setText("prof-lang", p.primary_language || "Tamil");

      // Contacts
      const contacts = p.family_and_contacts || {};
      const primary = contacts.primary_caregiver || {};
      setText("prof-cg-name", primary.name || "Ananya Narayanan");
      setText("prof-cg-phone", primary.phone || "+91 90000 12345");
      setText("prof-cg-schedule", primary.visit_schedule || "Visits every evening around 5:30 PM");
      setText("prof-cg-note", primary.status_note || "Works in Chennai and visits Lakshmi faithfully every evening.");

      const sec = contacts.secondary_contact || {};
      setText("prof-sec-name", sec.name || "Ravi Narayanan");
      setText("prof-sec-phone", sec.phone || "+91 90000 67890");
      setText("prof-sec-loc", sec.location || "Lives in Bengaluru, calls on Sunday mornings");

      const nurse = contacts.on_duty_nurse || {};
      setText("prof-nurse-name", nurse.name || "Care Team");
      setText("prof-nurse-ext", nurse.station_ext || "Chennai Home Care");
      setText("prof-nurse-notes", nurse.notes || "Supports morning medicines and daily routines");

      // Anchors
      const anchors = p.comfort_anchors || {};
      const pet = anchors.cherished_pet || {};
      if (pet.name) {
        setText("anchor-pet-title", `Cherished Pet: ${pet.name} (${pet.type || 'Dog'})`);
        setText("anchor-pet-desc", pet.memory_trigger || "Muthu is safe and happy at Ananya's house.");
      }
      if (anchors.favorite_meal) {
        setText("anchor-meal-desc", anchors.favorite_meal);
      }
      if (anchors.calming_phrase) {
        setText("prof-calming-phrase", `"${anchors.calming_phrase}"`);
      }

      // Guidelines
      const guidelines = p.care_guidelines || {};
      setText("prof-guideline-val", guidelines.validation_approach || "Always validate Lakshmi's feelings first.");
      setText("prof-guideline-ground", guidelines.grounding_strategy || "Remind gently of familiar constants.");
      setText("prof-guideline-limit", guidelines.response_length_limit || "Maximum 2-3 gentle sentences.");

    } catch (err) {
      console.warn("Could not hydrate patient profile:", err);
    }
  }

  // ==========================================================================
  // REAL-TIME STATUS POLLING (/api/caregiver/status)
  // ==========================================================================
  async function fetchStatus() {
    try {
      const response = await fetch("/api/caregiver/status");
      if (!response.ok) return;
      const data = await response.json();
      updateDashboard(data);
    } catch (e) {
      console.warn("Caregiver polling error:", e);
    }
  }

  function updateDashboard(data) {
    const risk = data.current_risk_level || "GREEN";
    const score = data.current_distress_score || 0;
    const activeAlerts = data.active_alerts || [];
    const recentEvents = data.recent_events || [];
    const connection = (data.patient && data.patient.connection) || {};
    const online = connection.status === "ONLINE";
    if (residentSessionBadge) {
      residentSessionBadge.textContent = `Patient ${online ? "ONLINE" : "OFFLINE"}`;
      residentSessionBadge.className = `status-pill ${online ? "status-pill-active" : ""}`;
    }
    if (patientConnectionStatus) {
      patientConnectionStatus.textContent = `Connection: ${online ? "ONLINE" : "OFFLINE"}`;
      patientConnectionStatus.style.color = online ? "var(--risk-green)" : "var(--text-muted)";
    }

    // Cache alerts for the dedicated Alerts page
    storedAlertsCache = activeAlerts;

    // 1. Update Risk Pill & Explanation
    riskPill.textContent = risk;
    riskPill.className = `risk-badge ${risk}`;

    if (risk === "RED") {
      riskExplanation.textContent = "Immediate caregiver check-in recommended. High conversational distress detected.";
      overallResidentState.textContent = "Action Required";
      overallResidentState.style.color = "var(--risk-red)";
    } else if (risk === "YELLOW") {
      riskExplanation.textContent = "Active monitoring state: repeated questions or moderate distress detected.";
      overallResidentState.textContent = "Needs Attention";
      overallResidentState.style.color = "var(--risk-yellow)";
    } else {
      riskExplanation.textContent = "Normal conversation with low distress. Safe and reassuring state.";
      overallResidentState.textContent = "Stable & Calm";
      overallResidentState.style.color = "var(--risk-green)";
    }

    // 2. Update Distress Score & Progress Bar
    distressScoreNum.textContent = score;
    distressBar.style.width = `${Math.min(100, Math.max(0, score))}%`;

    if (score >= 61) {
      distressBar.style.backgroundColor = "var(--risk-red)";
    } else if (score >= 31) {
      distressBar.style.backgroundColor = "var(--risk-yellow)";
    } else {
      distressBar.style.backgroundColor = "var(--risk-green)";
    }

    // 3. Extract Latest Signals & Repetition Information
    const latestEvent = recentEvents.length > 0 ? recentEvents[0] : null;
    if (latestEvent) {
      lastInteractionTime.textContent = formatTime(latestEvent.timestamp);

      // Repetition numbers
      const repCount = latestEvent.repetition_count || 0;
      repetitionCountNum.textContent = repCount;
      if (repCount >= 4) {
        repetitionLevelBadge.textContent = "HIGH";
        repetitionLevelBadge.className = "repetition-badge HIGH";
      } else if (repCount >= 2) {
        repetitionLevelBadge.textContent = "MEDIUM";
        repetitionLevelBadge.className = "repetition-badge MEDIUM";
      } else {
        repetitionLevelBadge.textContent = "NORMAL";
        repetitionLevelBadge.className = "repetition-badge";
      }

      // Repeated Topic extraction from reason or event
      const reason = latestEvent.reason || "";
      const topicMatch = reason.match(/regarding '([^']+)'/i);
      if (topicMatch && topicMatch[1]) {
        repetitionTopicVal.textContent = topicMatch[1];
      } else if (repCount > 0) {
        repetitionTopicVal.textContent = "Active Inquiry";
      } else {
        repetitionTopicVal.textContent = "None";
      }

      // Active Signal Tags
      const signals = latestEvent.signals || [];
      if (signals.length > 0) {
        activeSignalsContainer.innerHTML = signals.map(sig => `
          <span class="signal-badge">${escapeHtml(sig.replace(/_/g, " "))}</span>
        `).join("");
      } else {
        activeSignalsContainer.innerHTML = `<span class="signal-badge">Normal Telemetry</span>`;
      }
    } else {
      repetitionCountNum.textContent = "0";
      repetitionTopicVal.textContent = "None";
      activeSignalsContainer.innerHTML = `<span class="signal-badge">Awaiting Interaction</span>`;
    }

    // 4. Update Alerts Counters
    latestActiveCallSession = data.active_call_session || null;

    // Update live call session indicator if an active waiting session exists and caregiver is not currently connected
    if (latestActiveCallSession && (!peerConnection || peerConnection.connectionState === "closed")) {
      if (latestActiveCallSession.status === "WAITING" && (!activeSessionId || activeSessionId === latestActiveCallSession.session_id)) {
        if (callStatusBadge && callStatusBadge.textContent !== "CONNECTING" && callStatusBadge.textContent !== "CONNECTED") {
          setCallUiState("WAITING", `Escalation active: Live audio session ${latestActiveCallSession.session_id} ready to join.`);
        }
      }
    }

    const activeCount = activeAlerts.length;
    alertsCount.textContent = activeCount;
    alertsCountBadge.textContent = `${activeCount} Active`;
    alertsBadgeText.textContent = `${activeCount} Active`;
    sbAlertsBadge.textContent = activeCount;
    sbAlertsBadge.className = activeCount > 0 ? "nav-pill active-alert" : "nav-pill";
    alertSub.textContent = activeCount === 0 ? "Zero unacknowledged alerts" : "Caregiver attention required";

    // 5. Render Dashboard Active Alerts Feed
    renderDashboardAlerts(activeAlerts);

    // 6. Render Dashboard Live Conversational Turns
    renderTimeline(recentEvents);

    // 7. Render Dedicated Alerts Page
    renderAlertsPage(activeAlerts, recentEvents);

    refreshTime.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  // ==========================================================================
  // RENDER ALERTS ON DASHBOARD
  // ==========================================================================
  function renderDashboardAlerts(activeAlerts) {
    if (activeAlerts.length === 0) {
      alertsContainer.innerHTML = `
        <div class="empty-state" id="alerts-empty">
          <div class="empty-icon">🛡️</div>
          <p><strong>No active alerts.</strong> Resident interactions are within normal parameters.</p>
        </div>`;
      return;
    }

    alertsContainer.innerHTML = activeAlerts.map(alert => {
      const isRed = alert.risk_level === 'RED';
      const sessId = alert.session_id || (latestActiveCallSession ? latestActiveCallSession.session_id : '');
      return `
      <div class="alert-item ${isRed ? 'alert-item-red' : ''}" style="${isRed ? 'border-left: 4px solid var(--risk-red); background: #FEF2F2;' : ''}">
        <div class="alert-item-body">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <h4 style="${isRed ? 'color: var(--risk-red); font-weight: 700;' : ''}">${escapeHtml(alert.reason || "Escalation Alert")}</h4>
            <span class="badge ${isRed ? 'tag-red' : 'tag-yellow'}">${escapeHtml(alert.risk_level || 'ALERT')}</span>
          </div>
          <p><strong>Recommended:</strong> ${escapeHtml(alert.recommended_action || "Check in on resident.")}</p>
          <div class="alert-tags">
            <span class="alert-tag">Distress: ${alert.distress_score}/100</span>
            <span class="alert-tag">Repetition: ${alert.repetition_count}x</span>
            ${(alert.signals || []).map(sig => `<span class="alert-tag">${escapeHtml(sig.replace(/_/g, " "))}</span>`).join("")}
          </div>
        </div>
        <div class="alert-actions-col" style="display: flex; flex-direction: column; gap: 0.4rem; justify-content: center; align-items: flex-end;">
          ${isRed ? `
            <button class="call-action-btn-join alert-join-btn" data-session-id="${escapeHtml(sessId)}" style="background: #2563EB; color: #fff; border: none; padding: 0.5rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.35rem; white-space: nowrap; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
              </svg>
              <span>JOIN LIVE SESSION</span>
            </button>
          ` : ''}
          <button class="ack-btn" data-alert-id="${alert.alert_id}">Acknowledge</button>
        </div>
      </div>
    `}).join("");

    alertsContainer.querySelectorAll(".alert-join-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sessId = btn.getAttribute("data-session-id");
        const liveCallCard = document.getElementById("live-call-card");
        if (liveCallCard) liveCallCard.scrollIntoView({ behavior: "smooth" });
        await joinLiveSession(sessId);
      });
    });

    alertsContainer.querySelectorAll(".ack-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const alertId = btn.getAttribute("data-alert-id");
        btn.textContent = "Acknowledging...";
        btn.disabled = true;
        await acknowledgeAlert(alertId);
      });
    });
  }

  // ==========================================================================
  // RENDER DEDICATED ALERTS PAGE
  // ==========================================================================
  function renderAlertsPage(activeAlerts, recentEvents) {
    if (!alertsFeedList) return;

    alertsPageActiveCount.textContent = activeAlerts.length;
    alertsPageMonitoredCount.textContent = recentEvents.filter(e => e.risk_level === 'YELLOW').length;
    alertsPageAckCount.textContent = acknowledgedAlertsStore.size;

    let itemsToDisplay = [...activeAlerts];

    if (currentFilter === "active") {
      itemsToDisplay = activeAlerts.filter(a => !acknowledgedAlertsStore.has(a.alert_id));
    } else if (currentFilter === "acknowledged") {
      itemsToDisplay = Array.from(acknowledgedAlertsStore).map(id => ({
        alert_id: id,
        status: "ACKNOWLEDGED",
        reason: "Previously Acknowledged Escalation",
        recommended_action: "Caregiver verified resident status.",
        risk_level: "GREEN",
        distress_score: 0,
        repetition_count: 0,
        timestamp: new Date().toISOString()
      }));
    }

    if (itemsToDisplay.length === 0) {
      alertsFeedList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🛡️</div>
          <h4>No Escalation Alerts in this View</h4>
          <p>Resident interactions are currently within safe parameters.</p>
        </div>`;
      return;
    }

    alertsFeedList.innerHTML = itemsToDisplay.map(alert => {
      const isAck = acknowledgedAlertsStore.has(alert.alert_id) || alert.status === "ACKNOWLEDGED";
      const isRed = alert.risk_level === 'RED';
      const sessId = alert.session_id || (latestActiveCallSession ? latestActiveCallSession.session_id : '');
      return `
        <div class="alert-item" style="${isAck ? 'border-left-color: var(--risk-green); background: #F0FDF4;' : (isRed ? 'border-left-color: var(--risk-red); background: #FEF2F2;' : '')}">
          <div class="alert-item-body">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
              <h4 style="${isAck ? 'color: var(--risk-green-text);' : (isRed ? 'color: var(--risk-red); font-weight: 700;' : '')}">${escapeHtml(alert.reason || "Escalation Alert")}</h4>
              <span class="badge ${isAck ? 'suite-badge' : (isRed ? 'tag-red' : 'tag-yellow')}">${isAck ? 'ACKNOWLEDGED' : (alert.risk_level || 'RED')}</span>
            </div>
            <p><strong>Recommended Action:</strong> ${escapeHtml(alert.recommended_action || "Check in on resident room.")}</p>
            <div class="alert-tags">
              <span class="alert-tag">Distress: ${alert.distress_score || 0}/100</span>
              <span class="alert-tag">Repetition: ${alert.repetition_count || 0}x</span>
              <span class="alert-tag">Time: ${formatTime(alert.timestamp)}</span>
              ${(alert.signals || []).map(sig => `<span class="alert-tag">${escapeHtml(sig.replace(/_/g, " "))}</span>`).join("")}
            </div>
          </div>
          <div class="alert-actions-col" style="display: flex; flex-direction: column; gap: 0.4rem; justify-content: center; align-items: flex-end;">
            ${!isAck && isRed ? `
              <button class="call-action-btn-join alert-page-join-btn" data-session-id="${escapeHtml(sessId)}" style="background: #2563EB; color: #fff; border: none; padding: 0.5rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.35rem; white-space: nowrap; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                </svg>
                <span>JOIN LIVE SESSION</span>
              </button>
            ` : ''}
            ${!isAck ? `<button class="ack-btn" data-alert-id="${alert.alert_id}">Acknowledge</button>` : `<span class="suite-badge" style="font-size: 0.75rem;">Verified</span>`}
          </div>
        </div>
      `;
    }).join("");

    alertsFeedList.querySelectorAll(".alert-page-join-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sessId = btn.getAttribute("data-session-id");
        const dashTabBtn = document.querySelector('.nav-item[data-tab="dashboard"]');
        if (dashTabBtn) dashTabBtn.click();
        const liveCallCard = document.getElementById("live-call-card");
        if (liveCallCard) liveCallCard.scrollIntoView({ behavior: "smooth" });
        await joinLiveSession(sessId);
      });
    });

    alertsFeedList.querySelectorAll(".ack-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const alertId = btn.getAttribute("data-alert-id");
        btn.textContent = "Acknowledging...";
        btn.disabled = true;
        await acknowledgeAlert(alertId);
      });
    });
  }

  // Filter Pills Handling on Alerts Page
  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.getAttribute("data-filter") || "all";
      renderAlertsPage(storedAlertsCache, []);
    });
  });

  // ==========================================================================
  // RENDER TIMELINE
  // ==========================================================================
  function renderTimeline(recentEvents) {
    if (recentEvents.length === 0) {
      timelineContainer.innerHTML = `
        <div class="empty-state" id="timeline-empty">
          <div class="empty-icon">📞</div>
          <p><strong>Waiting for patient interactions.</strong> Press the green TALK button on the Phone Simulator to begin conversation.</p>
        </div>`;
      return;
    }

    timelineContainer.innerHTML = recentEvents.map(evt => `
      <div class="timeline-item">
        <div class="timeline-meta">
          <span>${formatTime(evt.timestamp)}</span>
          <span class="badge ${evt.risk_level === 'RED' ? 'tag-red' : (evt.risk_level === 'YELLOW' ? 'tag-yellow' : 'tag-green')}">
            ${evt.risk_level}
          </span>
        </div>
        <div class="turn-patient">
          <strong>Lakshmi:</strong> "${escapeHtml(evt.patient_message)}"
        </div>
        <div class="turn-companion">
          <strong>Companion:</strong> "${escapeHtml(evt.companion_reply)}"
        </div>
      </div>
    `).join("");
  }

  // ==========================================================================
  // ALERT ACKNOWLEDGMENT (/api/caregiver/acknowledge)
  // ==========================================================================
  async function acknowledgeAlert(alertId) {
    try {
      acknowledgedAlertsStore.add(alertId);
      const response = await fetch("/api/caregiver/acknowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: alertId }),
      });
      if (response.ok) {
        await fetchStatus();
      }
    } catch (e) {
      console.error("Failed to acknowledge alert:", e);
    }
  }

  // ==========================================================================
  // SYSTEM HEALTH DIAGNOSTICS (/api/health)
  // ==========================================================================
  async function checkSystemHealth() {
    try {
      const response = await fetch("/api/health");
      if (!response.ok) return;
      const data = await response.json();

      if (diagBackendStatus) {
        diagBackendStatus.textContent = "Connected (200 OK)";
      }

      if (diagGeminiStatus) {
        if (data.gemini_active) {
          diagGeminiStatus.textContent = "Google Gemini 2.5 Flash (Online)";
        } else {
          diagGeminiStatus.textContent = "Patient-Grounded Fallback Engine (Active)";
        }
      }
    } catch (e) {
      if (diagBackendStatus) {
        diagBackendStatus.textContent = "Disconnected / Reconnecting...";
        diagBackendStatus.style.color = "var(--risk-red)";
      }
    }
  }

  // ==========================================================================
  // HELPER UTILITIES
  // ==========================================================================
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatTime(iso) {
    if (!iso) return "Just now";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
      return iso;
    }
  }

  // ==========================================================================
  // WEBRTC LIVE INTERCOM CONTROLLER (CAREGIVER <-> PATIENT AUDIO)
  // ==========================================================================
  const btnJoinSession = document.getElementById("btn-join-session");
  const btnMute = document.getElementById("btn-mute");
  const btnEnd = document.getElementById("btn-end");
  const callStatusBadge = document.getElementById("call-status-badge");
  const callStatusDot = document.getElementById("call-status-dot");
  const callStatusText = document.getElementById("call-status-text");
  const callDuration = document.getElementById("call-duration");
  const remoteCaregiverAudio = document.getElementById("remote-caregiver-audio");

  let activeSessionId = null;
  let peerConnection = null;
  let localMediaStream = null;
  let callTimerInterval = null;
  let callStartTime = null;
  let signalingPollInterval = null;
  let processedPatientIceIndex = 0;
  let isMuted = false;

  function setCallUiState(status, message) {
    if (callStatusBadge) {
      callStatusBadge.textContent = status;
      if (status === "CONNECTED") {
        callStatusBadge.className = "badge tag-green";
        if (callStatusDot) callStatusDot.style.background = "#10B981";
      } else if (status === "CONNECTING" || status === "WAITING") {
        callStatusBadge.className = "badge tag-yellow";
        if (callStatusDot) callStatusDot.style.background = "#F59E0B";
      } else if (status === "FAILED") {
        callStatusBadge.className = "badge tag-red";
        if (callStatusDot) callStatusDot.style.background = "#EF4444";
      } else {
        callStatusBadge.className = "badge suite-badge";
        if (callStatusDot) callStatusDot.style.background = "#94A3B8";
      }
    }

    if (callStatusText && message) {
      callStatusText.textContent = message;
    }

    if (btnJoinSession && btnMute && btnEnd) {
      if (status === "CONNECTING" || status === "CONNECTED") {
        btnJoinSession.style.display = "none";
        btnMute.style.display = "inline-block";
        btnEnd.style.display = "inline-block";
      } else {
        btnJoinSession.style.display = "inline-flex";
        btnMute.style.display = "none";
        btnEnd.style.display = "none";
      }
    }

    if (status === "CONNECTED") {
      startCallTimer();
    } else if (status === "ENDED" || status === "FAILED" || status === "WAITING") {
      stopCallTimer();
    }
  }

  function startCallTimer() {
    if (callTimerInterval) clearInterval(callTimerInterval);
    callStartTime = Date.now();
    if (callDuration) callDuration.style.display = "inline-block";
    callTimerInterval = setInterval(() => {
      const elapsedSec = Math.floor((Date.now() - callStartTime) / 1000);
      const m = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
      const s = String(elapsedSec % 60).padStart(2, "0");
      if (callDuration) callDuration.textContent = `${m}:${s}`;
    }, 1000);
  }

  function stopCallTimer() {
    if (callTimerInterval) {
      clearInterval(callTimerInterval);
      callTimerInterval = null;
    }
    if (callDuration) {
      callDuration.style.display = "none";
      callDuration.textContent = "00:00";
    }
  }

  async function joinLiveSession(targetSessionId = null) {
    try {
      setCallUiState("CONNECTING", "Requesting microphone & initializing session...");

      // 1. Request microphone permission
      try {
        localMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        console.error("Microphone access failed:", err);
        setCallUiState("FAILED", "Microphone access denied or hardware unavailable.");
        return;
      }

      // 2. Resolve session ID:
      // If targetSessionId provided, use it.
      // Else check if an active waiting session exists on backend.
      // Else create a new session.
      let sessionIdToJoin = targetSessionId;
      if (!sessionIdToJoin) {
        try {
          const activeCheck = await fetch("/api/call/session/active?patient_id=PATIENT-84920");
          if (activeCheck.ok) {
            const activeData = await activeCheck.json();
            if (activeData.session && (activeData.session.status === "WAITING" || activeData.session.status === "CONNECTING")) {
              sessionIdToJoin = activeData.session.session_id;
            }
          }
        } catch (e) {
          console.warn("[WebRTC Caregiver] Active session check notice:", e);
        }
      }

      if (!sessionIdToJoin) {
        const sessionRes = await fetch("/api/call/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ patient_id: "PATIENT-84920" }),
        });
        if (!sessionRes.ok) throw new Error("Could not create call session.");
        const session = await sessionRes.json();
        sessionIdToJoin = session.session_id;
      }

      activeSessionId = sessionIdToJoin;

      // 3. Join as caregiver
      const joinRes = await fetch(`/api/call/session/${activeSessionId}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "caregiver" }),
      });
      if (!joinRes.ok) {
        const joinErr = await joinRes.json().catch(() => ({}));
        if (joinErr.error !== "Caregiver already joined this session") {
          throw new Error(joinErr.error || "Could not join call session as caregiver.");
        }
      }

      // 4. Initialize RTCPeerConnection with STUN
      peerConnection = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      processedPatientIceIndex = 0;

      // Add local audio track
      localMediaStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localMediaStream);
      });

      // Receive remote audio
      peerConnection.ontrack = (event) => {
        console.log("[WebRTC Caregiver] Received remote audio track.");
        if (remoteCaregiverAudio && event.streams[0]) {
          remoteCaregiverAudio.srcObject = event.streams[0];
          remoteCaregiverAudio.play().catch(e => console.warn("Remote audio play notice:", e));
        }
      };

      // Candidate handling
      peerConnection.onicecandidate = (event) => {
        if (event.candidate && activeSessionId) {
          sendCaregiverIce(activeSessionId, event.candidate);
        }
      };

      peerConnection.onconnectionstatechange = () => {
        const state = peerConnection.connectionState;
        console.log("[WebRTC Caregiver] Connection state:", state);
        if (state === "connected") {
          setCallUiState("CONNECTED", "Live human-to-resident audio connected.");
        } else if (state === "failed") {
          setCallUiState("FAILED", "WebRTC peer connection failed.");
          endLiveSession(false);
        } else if (state === "disconnected" || state === "closed") {
          setCallUiState("ENDED", "Session ended.");
          endLiveSession(false);
        }
      };

      // 5. Create offer
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      // 6. Submit offer to signaling
      await fetch(`/api/call/session/${activeSessionId}/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer: peerConnection.localDescription, role: "caregiver" }),
      });

      setCallUiState("WAITING", "Waiting for patient phone to answer...");

      // 7. Start polling for patient answer and ICE candidates
      startSignalingPoll(activeSessionId);

    } catch (e) {
      console.error("[WebRTC Caregiver] Live session error:", e);
      setCallUiState("FAILED", "Connection error: " + (e.message || e));
      endLiveSession(false);
    }
  }

  function startSignalingPoll(sessionId) {
    if (signalingPollInterval) clearInterval(signalingPollInterval);

    signalingPollInterval = setInterval(async () => {
      if (!sessionId || !peerConnection) return;

      try {
        const res = await fetch(`/api/call/session/${sessionId}`);
        if (!res.ok) return;
        const session = await res.json();

        // Check if session ended by patient
        if (session.status === "ENDED") {
          console.log("[WebRTC Caregiver] Session marked ENDED by patient.");
          setCallUiState("ENDED", "Patient ended the call.");
          endLiveSession(false);
          return;
        }

        // Apply patient answer if available and not yet applied
        if (session.answer && peerConnection && !peerConnection.remoteDescription) {
          console.log("[WebRTC Caregiver] Setting remote answer description.");
          await peerConnection.setRemoteDescription(new RTCSessionDescription(session.answer));
          setCallUiState("CONNECTING", "Patient answered! Negotiating audio...");
        }

        // Apply new patient ICE candidates
        const candidates = session.patient_ice_candidates || [];
        while (processedPatientIceIndex < candidates.length) {
          const candidateData = candidates[processedPatientIceIndex];
          if (peerConnection && peerConnection.remoteDescription) {
            await peerConnection.addIceCandidate(new RTCIceCandidate(candidateData));
          }
          processedPatientIceIndex++;
        }
      } catch (err) {
        console.warn("[WebRTC Caregiver] Polling notice:", err);
      }
    }, 800);
  }

  async function sendCaregiverIce(sessionId, candidate) {
    try {
      await fetch(`/api/call/session/${sessionId}/ice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate: candidate.toJSON ? candidate.toJSON() : candidate, role: "caregiver" }),
      });
    } catch (e) {
      console.warn("Failed to send caregiver ICE:", e);
    }
  }

  function toggleMute() {
    if (!localMediaStream) return;
    isMuted = !isMuted;
    localMediaStream.getAudioTracks().forEach(track => {
      track.enabled = !isMuted;
    });
    if (btnMute) {
      btnMute.textContent = isMuted ? "UNMUTE" : "MUTE";
      btnMute.style.background = isMuted ? "#EA580C" : "#475569";
    }
  }

  async function endLiveSession(notifyBackend = true) {
    if (signalingPollInterval) {
      clearInterval(signalingPollInterval);
      signalingPollInterval = null;
    }

    if (notifyBackend && activeSessionId) {
      try {
        await fetch(`/api/call/session/${activeSessionId}/end`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: "caregiver" }),
        });
      } catch (e) {
        console.warn("Could not notify backend of call end:", e);
      }
    }

    if (localMediaStream) {
      localMediaStream.getTracks().forEach(t => t.stop());
      localMediaStream = null;
    }

    if (peerConnection) {
      peerConnection.close();
      peerConnection = null;
    }

    if (remoteCaregiverAudio) {
      remoteCaregiverAudio.srcObject = null;
    }

    activeSessionId = null;
    processedPatientIceIndex = 0;
    isMuted = false;
    if (btnMute) {
      btnMute.textContent = "MUTE";
      btnMute.style.background = "#475569";
    }

    setCallUiState("ENDED", "Live audio session terminated.");
    setTimeout(() => {
      setCallUiState("WAITING", "Ready for live human-to-resident audio communication.");
    }, 3000);
  }

  if (btnJoinSession) btnJoinSession.addEventListener("click", joinLiveSession);
  if (btnMute) btnMute.addEventListener("click", toggleMute);
  if (btnEnd) btnEnd.addEventListener("click", () => endLiveSession(true));

  // ==========================================================================
  // INITIALIZATION & RECURRING POLLING
  // ==========================================================================
  hydratePatientProfile();
  fetchStatus();
  checkSystemHealth();

  // Poll status every 2.5 seconds
  setInterval(fetchStatus, 2500);

  // Poll health diagnostics every 15 seconds
  setInterval(checkSystemHealth, 15000);
});
