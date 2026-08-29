/**
 * MerchantOS AI — Dynamic Frontend Layer (Phase 10)
 * Server-Sent Events (SSE) Live Feed, Real-Time Trace Timeline, and Demo Console
 * Zero external dependencies, pure vanilla ES6
 */

(function () {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Helper: Escape HTML string to prevent XSS
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Helper: Format paise minor units to INR
    function formatInr(paise) {
        if (paise === null || paise === undefined || isNaN(paise)) return '—';
        const num = Number(paise) / 100;
        return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Connect SSE with EventSource and event handlers
    function connectSSE(url, onTradeEvent, onOpen, onError) {
        const evtSource = new EventSource(url);

        evtSource.onopen = function (e) {
            if (onOpen) onOpen(e);
        };

        evtSource.addEventListener('trade', function (e) {
            try {
                const data = JSON.parse(e.data);
                if (onTradeEvent) onTradeEvent(data);
            } catch (err) {
                console.error('[SSE Parse Error]', err, e.data);
            }
        });

        evtSource.onerror = function (e) {
            if (onError) onError(e);
        };

        return evtSource;
    }

    // ==========================================
    // 1. REGISTRY PAGE (/dashboard)
    // ==========================================
    function initRegistryPage() {
        const tableBody = document.getElementById('registry-table-body');
        const emptyState = document.getElementById('registry-empty-state');
        const tableElement = document.getElementById('registry-table');
        if (!tableBody) return;

        // Fetch latest KPI summary
        function updateSummaryKPIs() {
            fetch('/api/summary')
                .then(r => r.json())
                .then(data => {
                    const elTotal = document.getElementById('kpi-total-sessions');
                    const elConv = document.getElementById('kpi-converted');
                    const elBlock = document.getElementById('kpi-blocked');
                    const elDecl = document.getElementById('kpi-declined');

                    if (elTotal && data.total_sessions !== undefined) elTotal.textContent = data.total_sessions;
                    if (elConv && data.converted !== undefined) elConv.textContent = data.converted;
                    if (elBlock && data.blocked !== undefined) elBlock.textContent = data.blocked;
                    if (elDecl && data.declined !== undefined) elDecl.textContent = data.declined;
                })
                .catch(err => console.error('[KPI Fetch Error]', err));
        }

        connectSSE('/api/events', function (evt) {
            if (emptyState) emptyState.style.display = 'none';
            if (tableElement) tableElement.style.display = 'table';

            const sessionId = evt.session_id;
            let payload = {};
            try {
                payload = typeof evt.payload === 'string' ? JSON.parse(evt.payload) : evt.payload;
            } catch (_) {}

            let existingRow = document.getElementById(`row-${sessionId}`);
            if (existingRow) {
                // Update existing row
                const cells = existingRow.querySelectorAll('td');
                if (cells.length >= 6) {
                    const currentEvents = parseInt(cells[2].textContent, 10) || 0;
                    cells[2].textContent = currentEvents + 1;

                    if (evt.event_type === 'gate_decision' && payload.action) {
                        const act = payload.action;
                        const badgeClass = act === 'EXECUTE' ? 'tag-success' : act === 'REPAIR' ? 'tag-warning' : 'tag-danger';
                        cells[3].innerHTML = `<span class="badge-tag ${badgeClass}">${escapeHtml(act)}</span>`;
                        if (payload.final_offer && payload.final_offer.proposed_price_minor) {
                            cells[4].textContent = formatInr(payload.final_offer.proposed_price_minor);
                        }
                    } else if (evt.event_type === 'order_created') {
                        if (payload.amount) cells[4].textContent = formatInr(payload.amount);
                    } else if (evt.event_type === 'payment_captured') {
                        cells[5].innerHTML = `<span class="badge-tag tag-success">Converted</span>`;
                        if (payload.amount_minor) cells[4].textContent = formatInr(payload.amount_minor);
                    } else if (evt.event_type === 'error') {
                        cells[5].innerHTML = `<span class="badge-tag tag-danger">Security Alert</span>`;
                    }
                }
            } else {
                // Prepend new row
                const tr = document.createElement('tr');
                tr.id = `row-${sessionId}`;
                if (!prefersReducedMotion) {
                    tr.style.opacity = '0';
                    tr.style.transform = 'translateY(-8px)';
                    tr.style.transition = 'opacity 240ms ease-out, transform 240ms ease-out';
                }

                let gateBadge = '<span class="badge-tag tag-neutral">N/A</span>';
                let amountText = '—';
                let statusBadge = '<span class="badge-tag tag-accent">In Negotiation</span>';

                if (evt.event_type === 'gate_decision' && payload.action) {
                    const act = payload.action;
                    const badgeClass = act === 'EXECUTE' ? 'tag-success' : act === 'REPAIR' ? 'tag-warning' : 'tag-danger';
                    gateBadge = `<span class="badge-tag ${badgeClass}">${escapeHtml(act)}</span>`;
                }

                tr.innerHTML = `
                    <td>
                        <a href="/dashboard/trace/${escapeHtml(sessionId)}" style="font-family: var(--font-mono); font-weight: 600; color: var(--accent); text-decoration: none;">
                            ${escapeHtml(sessionId)}
                        </a>
                    </td>
                    <td class="tabular-nums">1</td>
                    <td class="tabular-nums">1</td>
                    <td>${gateBadge}</td>
                    <td style="font-family: var(--font-mono); font-weight: 600;">${amountText}</td>
                    <td>${statusBadge}</td>
                    <td style="text-align: right;">
                        <a href="/dashboard/trace/${escapeHtml(sessionId)}" class="btn btn-outline" style="padding: 4px 10px; font-size: 12px;">
                            Inspect &rarr;
                        </a>
                    </td>
                `;

                tableBody.insertBefore(tr, tableBody.firstChild);
                if (!prefersReducedMotion) {
                    requestAnimationFrame(() => {
                        tr.style.opacity = '1';
                        tr.style.transform = 'translateY(0)';
                    });
                }
            }

            updateSummaryKPIs();
        });
    }

    // ==========================================
    // 2. TRACE PAGE (/dashboard/trace/{session_id})
    // ==========================================
    function initTracePage() {
        const traceView = document.getElementById('trace-view');
        const timeline = document.getElementById('trace-timeline');
        if (!traceView || !timeline) return;

        const sessionId = traceView.getAttribute('data-session-id');
        if (!sessionId) return;

        connectSSE(`/api/events?session_id=${encodeURIComponent(sessionId)}`, function (evt) {
            let payload = {};
            try {
                payload = typeof evt.payload === 'string' ? JSON.parse(evt.payload) : evt.payload;
            } catch (_) {}

            // Update Total Events Count
            const elTotal = document.getElementById('trace-total-events');
            if (elTotal) {
                const cur = parseInt(elTotal.textContent, 10) || 0;
                elTotal.textContent = cur + 1;
            }

            // Update Timestamp
            const elTs = document.getElementById('trace-last-timestamp');
            if (elTs && evt.timestamp) elTs.textContent = evt.timestamp;

            // Determine Phase & Styling
            let phaseName = 'Phase: Audit Log';
            let phaseClass = 'card-phase-audit';
            let gateHighlight = '';

            if (evt.event_type === 'intent_received' || evt.event_type === 'offer_proposed') {
                phaseName = 'Phase A: Intent & Negotiation';
                phaseClass = 'card-phase-negotiation';
            } else if (evt.event_type === 'gate_decision') {
                phaseName = 'Phase B: The Gate (CommerceProof Control)';
                phaseClass = 'card-phase-gate';
                const act = payload.action || 'EXECUTE';
                gateHighlight = act === 'EXECUTE' ? 'gate-execute' : act === 'REPAIR' ? 'gate-repair' : 'gate-block';

                const elGate = document.getElementById('trace-gate-action');
                if (elGate) {
                    const col = act === 'EXECUTE' ? 'var(--success)' : act === 'REPAIR' ? 'var(--warning)' : 'var(--danger)';
                    elGate.innerHTML = `<span style="color: ${col};">${escapeHtml(act)}</span>`;
                }
            } else if (evt.event_type === 'order_created') {
                phaseName = 'Phase C: Execution (Razorpay Order)';
                phaseClass = 'card-phase-execution';
                const elAmt = document.getElementById('trace-settled-amount');
                if (elAmt && payload.amount) elAmt.textContent = formatInr(payload.amount);
            } else if (evt.event_type === 'payment_captured') {
                phaseName = 'Phase D: Settlement & Audit';
                phaseClass = 'card-phase-settlement';
                const elAmt = document.getElementById('trace-settled-amount');
                if (elAmt && payload.amount_minor) elAmt.textContent = formatInr(payload.amount_minor);
                const elBadge = document.getElementById('trace-header-badge');
                if (elBadge) elBadge.innerHTML = '<span class="badge-tag tag-success" style="font-size: 12px; padding: 6px 12px;">Converted</span>';
            } else if (evt.event_type === 'error') {
                phaseName = 'Phase: Security Protection';
                phaseClass = 'card-phase-settlement';
                const elBadge = document.getElementById('trace-header-badge');
                if (elBadge) elBadge.innerHTML = '<span class="badge-tag tag-danger" style="font-size: 12px; padding: 6px 12px;">Security Alert</span>';
            }

            // Create Event Card
            const card = document.createElement('div');
            card.className = `trace-card ${phaseClass} ${gateHighlight}`;
            if (!prefersReducedMotion) {
                card.style.opacity = '0';
                card.style.transform = 'translateY(10px)';
                card.style.transition = 'opacity 240ms ease-out, transform 240ms ease-out';
            }

            let customSnippet = '';
            if (evt.event_type === 'intent_received') {
                customSnippet = `
                    <div style="background: #FAFAF8; border: 1px solid var(--hairline); border-radius: 6px; padding: 12px 16px; margin: 8px 0;">
                        <div style="font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 4px;">Buyer Utterance</div>
                        <div style="font-size: 14px; font-style: italic; color: var(--ink);">"${escapeHtml(payload.nl_utterance || '—')}"</div>
                    </div>
                `;
            } else if (evt.event_type === 'offer_proposed') {
                customSnippet = `
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; background: #FAFAF8; border: 1px solid var(--hairline); border-radius: 6px; padding: 12px 16px; margin: 8px 0;">
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600;">Proposed SKU</div>
                            <div style="font-family: var(--font-mono); font-size: 13px; font-weight: 600;">${escapeHtml(payload.selected_sku_id || payload.sku_id || '—')}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600;">Proposed Price</div>
                            <div style="font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--accent);">${formatInr(payload.proposed_price_minor)}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600;">Discount</div>
                            <div style="font-family: var(--font-mono); font-size: 13px;">${formatInr(payload.discount_minor)}</div>
                        </div>
                    </div>
                `;
            } else if (evt.event_type === 'gate_decision') {
                customSnippet = `
                    <div style="background: #FAFAF8; border: 1px solid var(--hairline); border-radius: 6px; padding: 12px 16px; margin: 8px 0;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600;">CommerceProof Decision</span>
                            <span style="font-family: var(--font-mono); font-size: 11px; color: var(--accent);">Hash: ${escapeHtml(payload.state_hash || 'None')}</span>
                        </div>
                    </div>
                `;
            } else if (evt.event_type === 'payment_captured') {
                customSnippet = `
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; background: #ECFDF3; border: 1px solid rgba(21, 128, 61, 0.2); border-radius: 6px; padding: 12px 16px; margin: 8px 0;">
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: var(--success); font-weight: 600;">Payment ID</div>
                            <div style="font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--success);">${escapeHtml(payload.payment_id || '—')}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: var(--success); font-weight: 600;">Captured Amount</div>
                            <div style="font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--success);">${formatInr(payload.amount_minor)}</div>
                        </div>
                    </div>
                `;
            }

            const rawJsonStr = JSON.stringify(payload, null, 2);

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="eyebrow" style="margin-bottom: 0; color: var(--ink);">${escapeHtml(phaseName)}</span>
                        <span class="badge-tag tag-neutral" style="font-family: var(--font-mono);">${escapeHtml(evt.event_type)}</span>
                    </div>
                    <div style="font-size: 11px; color: var(--muted); font-family: var(--font-mono);">
                        ${escapeHtml(evt.event_id)} &middot; ${escapeHtml(evt.timestamp)}
                    </div>
                </div>
                ${customSnippet}
                <details class="raw-payload-box">
                    <summary>Inspect Raw JSON Event Payload &middot; ${escapeHtml(evt.event_type)}</summary>
                    <pre><code>${escapeHtml(rawJsonStr)}</code></pre>
                </details>
            `;

            // Auto-scroll check
            const shouldScroll = (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 180);

            timeline.appendChild(card);

            if (!prefersReducedMotion) {
                requestAnimationFrame(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                });
            }

            if (shouldScroll) {
                window.scrollTo({ top: document.body.scrollHeight, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
            }
        });
    }

    // ==========================================
    // 3. DEMO CONSOLE (/demo)
    // ==========================================
    function initDemoConsole() {
        const utteranceInput = document.getElementById('demo-utterance');
        const charCounter = document.getElementById('char-counter');
        const terminal = document.getElementById('demo-log-terminal');
        const openTraceBtn = document.getElementById('open-trace-btn');
        if (!utteranceInput || !terminal) return;

        // Live Character Counter
        function updateCharCount() {
            if (charCounter) {
                const len = utteranceInput.value.length;
                charCounter.textContent = `${len}/500`;
                charCounter.style.color = len >= 480 ? 'var(--danger)' : 'var(--muted)';
            }
        }
        utteranceInput.addEventListener('input', updateCharCount);
        updateCharCount();

        let activeEvtSource = null;

        function logToTerminal(badgeText, badgeClass, message, rawData) {
            const row = document.createElement('div');
            row.style.marginBottom = '10px';
            if (!prefersReducedMotion) {
                row.style.opacity = '0';
                row.style.transform = 'translateY(4px)';
                row.style.transition = 'opacity 180ms ease-out, transform 180ms ease-out';
            }

            const timeStr = new Date().toLocaleTimeString('en-GB');
            let dataStr = '';
            if (rawData) {
                try {
                    const parsed = typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
                    dataStr = `<pre style="margin-top: 4px; padding: 6px 10px; background: rgba(0,0,0,0.03); border-radius: 4px; font-size: 11px; overflow-x: auto;">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
                } catch (_) {}
            }

            row.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span style="color: var(--muted); font-size: 11px;">[${escapeHtml(timeStr)}]</span>
                    <span class="badge-tag ${badgeClass}" style="font-size: 10px; padding: 2px 6px;">${escapeHtml(badgeText)}</span>
                    <span style="color: var(--ink); font-weight: 500;">${escapeHtml(message)}</span>
                </div>
                ${dataStr}
            `;

            terminal.appendChild(row);
            if (!prefersReducedMotion) {
                requestAnimationFrame(() => {
                    row.style.opacity = '1';
                    row.style.transform = 'translateY(0)';
                });
            }

            terminal.scrollTop = terminal.scrollHeight;
        }

        function triggerScenario(url, body) {
            if (activeEvtSource) {
                activeEvtSource.close();
                activeEvtSource = null;
            }

            terminal.innerHTML = '';
            logToTerminal('DISPATCH', 'tag-accent', `Initiating scenario trigger via ${url}...`);

            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body ? JSON.stringify(body) : JSON.stringify({}),
            })
                .then(async res => {
                    if (!res.ok) {
                        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
                        throw new Error(errJson.detail || `Server error (${res.status})`);
                    }
                    return res.json();
                })
                .then(data => {
                    const sessionId = data.session_id;
                    logToTerminal('SESSION', 'tag-success', `Session initialized: ${sessionId} (Mode: ${data.mode})`);

                    if (openTraceBtn) {
                        openTraceBtn.href = `/dashboard/trace/${encodeURIComponent(sessionId)}`;
                        openTraceBtn.style.display = 'inline-flex';
                    }

                    // Subscribe to live SSE filtered to this session
                    activeEvtSource = connectSSE(`/api/events?session_id=${encodeURIComponent(sessionId)}`, function (evt) {
                        let p = {};
                        try { p = typeof evt.payload === 'string' ? JSON.parse(evt.payload) : evt.payload; } catch (_) {}

                        if (evt.event_type === 'intent_received') {
                            logToTerminal('01 INTENT', 'tag-neutral', `Buyer: "${p.nl_utterance || '—'}"`, p);
                        } else if (evt.event_type === 'offer_proposed') {
                            const isLive = p.live_llm ? ' (Live LLM)' : ' (Mock LLM)';
                            logToTerminal('02 AGENT', 'tag-accent', `Proposed ${p.selected_sku_id || 'SKU'} at ${formatInr(p.proposed_price_minor)}${isLive}`, p);
                        } else if (evt.event_type === 'gate_decision') {
                            const act = p.action || 'EXECUTE';
                            const tagClass = act === 'EXECUTE' ? 'tag-success' : act === 'REPAIR' ? 'tag-warning' : 'tag-danger';
                            logToTerminal('03 GATE', tagClass, `CommerceProof Action: [${act}] (Hash: ${(p.state_hash || '').substring(0, 16)}...)`, p);
                        } else if (evt.event_type === 'order_created') {
                            logToTerminal('04 EXECUTE', 'tag-neutral', `Razorpay Order Created: ${p.order_id} for ${formatInr(p.amount)}`, p);
                        } else if (evt.event_type === 'payment_captured') {
                            logToTerminal('05 SETTLE', 'tag-success', `Payment Captured: ${p.payment_id} (HMAC Verified)`, p);
                        } else if (evt.event_type === 'error') {
                            logToTerminal('ALERT', 'tag-danger', `Security Event: ${p.error || p.error_type || 'Error'} &mdash; ${p.message || ''}`, p);
                        } else {
                            logToTerminal('EVENT', 'tag-neutral', `${evt.event_type}`, p);
                        }
                    });
                })
                .catch(err => {
                    logToTerminal('ERROR', 'tag-danger', `Scenario Failed: ${err.message}`);
                });
        }

        // Button Listeners
        const btnMock = document.getElementById('btn-negotiate-mock');
        if (btnMock) {
            btnMock.addEventListener('click', () => {
                const val = utteranceInput.value.trim();
                if (!val) { alert('Please enter a buyer utterance'); return; }
                triggerScenario('/api/demo/negotiate', { utterance: val, use_live_llm: false });
            });
        }

        const btnLive = document.getElementById('btn-negotiate-live');
        if (btnLive) {
            btnLive.addEventListener('click', () => {
                const val = utteranceInput.value.trim();
                if (!val) { alert('Please enter a buyer utterance'); return; }
                triggerScenario('/api/demo/negotiate', { utterance: val, use_live_llm: true });
            });
        }

        const btnInj = document.getElementById('btn-attack-injection');
        if (btnInj) {
            btnInj.addEventListener('click', () => {
                triggerScenario('/api/demo/injection', {});
            });
        }

        const btnMut = document.getElementById('btn-attack-mutation');
        if (btnMut) {
            btnMut.addEventListener('click', () => {
                triggerScenario('/api/demo/cart-mutation', {});
            });
        }

        const btnLiveOrd = document.getElementById('btn-live-order');
        if (btnLiveOrd) {
            btnLiveOrd.addEventListener('click', () => {
                triggerScenario('/api/demo/live-order', {});
            });
        }
    }

    // ==========================================
    // 4. VALIDATION CENTER (/validation)
    // ==========================================
    function initValidationPage() {
        const tableBody = document.getElementById('validation-table-body');
        const emptyRow = document.getElementById('val-empty-row');
        const statusPill = document.getElementById('overall-status-pill');
        const liveDot = document.getElementById('validation-live-dot');
        const runningLabel = document.getElementById('validation-running-label');
        const lastRunScope = document.getElementById('last-run-scope');
        const lastRunTime = document.getElementById('last-run-time');
        if (!tableBody) return;

        let activeValSource = null;

        function renderCheckRow(res) {
            if (emptyRow) emptyRow.style.display = 'none';

            let row = document.getElementById(`check-row-${res.check_id}`);
            if (!row) {
                row = document.createElement('tr');
                row.id = `check-row-${res.check_id}`;
                if (!prefersReducedMotion) {
                    row.style.opacity = '0';
                    row.style.transform = 'translateY(-6px)';
                    row.style.transition = 'opacity 240ms ease-out, transform 240ms ease-out';
                }
                tableBody.appendChild(row);
            }

            let catBadge = '<span class="badge-tag tag-accent">hermetic</span>';
            if (res.category === 'live_razorpay') {
                catBadge = '<span class="badge-tag tag-warning">live_razorpay</span>';
            } else if (res.category === 'live_llm') {
                catBadge = '<span class="badge-tag tag-neutral">live_llm</span>';
            }

            let statusBadge = '<span class="badge-tag tag-neutral">SKIPPED</span>';
            if (res.status === 'pass') {
                statusBadge = '<span class="badge-tag tag-success"><span class="status-dot-sm"></span> PASS</span>';
            } else if (res.status === 'fail') {
                statusBadge = '<span class="badge-tag tag-danger"><span class="status-dot-sm"></span> FAIL</span>';
            }

            const latencyStr = (res.latency_ms !== null && res.latency_ms !== undefined) ? `${res.latency_ms}ms` : '—';
            const timeStr = res.timestamp && res.timestamp.length >= 19 ? res.timestamp.substring(11, 19) : res.timestamp;

            let evidenceHtml = '';
            if (res.evidence_json) {
                evidenceHtml = `<div style="font-family: var(--font-mono); font-size: 11px; color: var(--muted); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(res.evidence_json)}">${escapeHtml(res.evidence_json)}</div>`;
            }

            row.innerHTML = `
                <td>
                    <div style="font-weight: 600; color: var(--ink);">${escapeHtml(res.name)}</div>
                    <div style="font-size: 11px; color: var(--muted); font-family: var(--font-mono);">${escapeHtml(res.check_id)}</div>
                </td>
                <td>${catBadge}</td>
                <td>${statusBadge}</td>
                <td class="tabular-nums" style="font-family: var(--font-mono); font-size: 12px;">${escapeHtml(latencyStr)}</td>
                <td>
                    <div style="font-size: 12px; color: var(--ink); margin-bottom: 2px;">${escapeHtml(res.detail)}</div>
                    ${evidenceHtml}
                </td>
                <td style="text-align: right; font-family: var(--font-mono); font-size: 11px; color: var(--muted);">${escapeHtml(timeStr)}</td>
            `;

            if (!prefersReducedMotion) {
                requestAnimationFrame(() => {
                    row.style.opacity = '1';
                    row.style.transform = 'translateY(0)';
                });
            }
        }

        function triggerValidation(scope) {
            if (activeValSource) {
                activeValSource.close();
                activeValSource = null;
            }

            if (statusPill) statusPill.innerHTML = '<span class="badge-tag tag-accent" style="font-size: 12px; padding: 6px 14px;">STATUS: RUNNING</span>';
            if (liveDot) liveDot.style.display = 'inline-block';
            if (runningLabel) runningLabel.style.display = 'inline';
            if (lastRunScope) lastRunScope.textContent = scope.toUpperCase();

            // Clear table
            tableBody.innerHTML = '';

            fetch('/api/validation/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scope: scope }),
            })
                .then(r => r.json())
                .then(data => {
                    let hasFailures = false;
                    const eventSource = new EventSource('/api/validation/events');
                    activeValSource = eventSource;

                    eventSource.addEventListener('check', function (e) {
                        try {
                            const res = JSON.parse(e.data);
                            if (res.status === 'fail') hasFailures = true;
                            renderCheckRow(res);
                        } catch (err) {
                            console.error('[Validation Parse Error]', err);
                        }
                    });

                    eventSource.addEventListener('done', function (e) {
                        if (activeValSource) {
                            activeValSource.close();
                            activeValSource = null;
                        }
                        if (liveDot) liveDot.style.display = 'none';
                        if (runningLabel) runningLabel.style.display = 'none';
                        if (statusPill) {
                            const finalTag = hasFailures ? 'tag-danger' : 'tag-success';
                            const finalTxt = hasFailures ? 'STATUS: FAIL' : 'STATUS: PASS';
                            statusPill.innerHTML = `<span class="badge-tag ${finalTag}" style="font-size: 12px; padding: 6px 14px;">${finalTxt}</span>`;
                        }
                        if (lastRunTime) lastRunTime.textContent = new Date().toISOString().substring(0, 19) + 'Z';
                    });

                    // Timeout fallback to complete status
                    setTimeout(() => {
                        if (liveDot) liveDot.style.display = 'none';
                        if (runningLabel) runningLabel.style.display = 'none';
                        if (statusPill && statusPill.textContent.includes('RUNNING')) {
                            const finalTag = hasFailures ? 'tag-danger' : 'tag-success';
                            const finalTxt = hasFailures ? 'STATUS: FAIL' : 'STATUS: PASS';
                            statusPill.innerHTML = `<span class="badge-tag ${finalTag}" style="font-size: 12px; padding: 6px 14px;">${finalTxt}</span>`;
                        }
                    }, 6000);
                })
                .catch(err => {
                    console.error('[Validation Run Trigger Error]', err);
                    if (liveDot) liveDot.style.display = 'none';
                    if (runningLabel) runningLabel.style.display = 'none';
                    if (statusPill) statusPill.innerHTML = '<span class="badge-tag tag-danger" style="font-size: 12px; padding: 6px 14px;">STATUS: ERROR</span>';
                });
        }

        const btnHermetic = document.getElementById('btn-run-hermetic');
        if (btnHermetic) btnHermetic.addEventListener('click', () => triggerValidation('hermetic'));

        const btnRazorpay = document.getElementById('btn-run-razorpay');
        if (btnRazorpay) btnRazorpay.addEventListener('click', () => triggerValidation('live'));

        const btnLlm = document.getElementById('btn-run-llm');
        if (btnLlm) btnLlm.addEventListener('click', () => triggerValidation('live'));

        const btnAll = document.getElementById('btn-run-all');
        if (btnAll) btnAll.addEventListener('click', () => triggerValidation('all'));
    }

    // Initialize Components on DOM Load
    document.addEventListener('DOMContentLoaded', () => {
        initRegistryPage();
        initTracePage();
        initDemoConsole();
        initValidationPage();
    });
})();
