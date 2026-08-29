/**
 * The Trading Floor (Phase 12) Live Theatre Choreography Client
 * Pure Vanilla JS, No external libraries.
 */

(function () {
    'use strict';

    let currentEventSource = null;
    let selectedMode = 'solo';
    let currentSessionId = null;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Currency Formatter
    function formatINR(paise) {
        if (paise === null || paise === undefined) return '—';
        const num = Number(paise);
        if (isNaN(num)) return String(paise);
        return '₹' + (num / 100).toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // Tabular count-up animation
    function animateCountUp(element, targetVal, prefix = '', suffix = '', isCurrency = false) {
        if (!element) return;
        if (prefersReducedMotion) {
            element.textContent = isCurrency ? formatINR(targetVal) : `${prefix}${targetVal}${suffix}`;
            return;
        }

        let start = 0;
        const duration = 400; // ms
        const startTime = performance.now();

        function update(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (targetVal - start) * easeOut);

            element.textContent = isCurrency ? formatINR(current) : `${prefix}${current}${suffix}`;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        requestAnimationFrame(update);
    }

    // DOM References
    const utteranceInput = document.getElementById('theater-utterance');
    const runBtn = document.getElementById('btn-run-trade');
    const randomBtn = document.getElementById('btn-random-buyer');
    const modeSoloBtn = document.getElementById('mode-solo');
    const modeRaceBtn = document.getElementById('mode-race');
    const liveLlmToggle = document.getElementById('toggle-live-llm');
    const statusLabel = document.getElementById('theater-status-label');
    const liveDot = document.getElementById('theater-live-indicator');
    const narrationRail = document.getElementById('narration-rail');
    const outcomeStrip = document.getElementById('theater-outcome-strip');
    const revealBox = document.getElementById('evaluator-reveal-box');
    const raceBar = document.getElementById('race-comparison-bar');

    // Actor DOM Cards
    const actorCards = {
        buyer: document.getElementById('actor-buyer'),
        clerk: document.getElementById('actor-clerk'),
        salesperson: document.getElementById('actor-salesperson'),
        accountant: document.getElementById('actor-accountant'),
        bank: document.getElementById('actor-bank'),
    };

    const actorScreens = {
        buyer: document.getElementById('screen-buyer'),
        clerk: document.getElementById('screen-clerk'),
        salesperson: document.getElementById('screen-salesperson'),
        accountant: document.getElementById('screen-accountant'),
        bank: document.getElementById('screen-bank'),
    };

    // Mode Switcher
    if (modeSoloBtn && modeRaceBtn) {
        modeSoloBtn.addEventListener('click', () => setMode('solo'));
        modeRaceBtn.addEventListener('click', () => setMode('race'));
    }

    function setMode(mode) {
        selectedMode = mode;
        if (mode === 'solo') {
            modeSoloBtn.classList.add('active');
            modeRaceBtn.classList.remove('active');
            if (actorCards.clerk) actorCards.clerk.style.opacity = '0.45';
            if (raceBar) raceBar.style.display = 'none';
        } else {
            modeRaceBtn.classList.add('active');
            modeSoloBtn.classList.remove('active');
            if (actorCards.clerk) actorCards.clerk.style.opacity = '1';
            if (raceBar) raceBar.style.display = 'grid';
        }
    }

    // Reset Stage
    function resetStage() {
        Object.values(actorCards).forEach(card => {
            if (!card) return;
            card.classList.remove('actor-acting', 'actor-done');
        });

        // Reset screens
        if (actorScreens.buyer) actorScreens.buyer.innerHTML = '<div class="screen-placeholder">Awaiting buyer input...</div>';
        if (actorScreens.clerk) actorScreens.clerk.innerHTML = selectedMode === 'solo' ? '<div class="screen-placeholder">Passive in Solo mode</div>' : '<div class="screen-placeholder">Awaiting intent parse...</div>';
        if (actorScreens.salesperson) actorScreens.salesperson.innerHTML = '<div class="screen-placeholder">Awaiting intent broadcast...</div>';
        if (actorScreens.accountant) actorScreens.accountant.innerHTML = '<div class="screen-placeholder">Boundary gate armed...</div>';
        if (actorScreens.bank) actorScreens.bank.innerHTML = '<div class="screen-placeholder">Ready for authorized order...</div>';

        // Clear connectors
        for (let i = 1; i <= 4; i++) {
            const conn = document.getElementById(`connector-${i}`);
            if (conn) conn.classList.remove('connector-active');
        }

        if (narrationRail) narrationRail.innerHTML = '';
        if (outcomeStrip) outcomeStrip.style.display = 'none';
        if (revealBox) revealBox.style.display = 'none';
    }

    // Set Active Actor
    function setActiveActor(actorKey, connectorIdx = null) {
        Object.entries(actorCards).forEach(([k, card]) => {
            if (!card) return;
            if (k === actorKey) {
                card.classList.add('actor-acting');
                card.classList.remove('actor-done');
            } else if (card.classList.contains('actor-acting')) {
                card.classList.remove('actor-acting');
                card.classList.add('actor-done');
            }
        });

        if (connectorIdx && !prefersReducedMotion) {
            const conn = document.getElementById(`connector-${connectorIdx}`);
            if (conn) {
                conn.classList.add('connector-active');
                setTimeout(() => conn.classList.remove('connector-active'), 600);
            }
        }
    }

    // Append Narration Line
    function appendNarration(actor, title, caption, tone) {
        if (!narrationRail) return;

        const line = document.createElement('div');
        line.className = `narration-line tone-${tone}`;

        let actorDotColor = 'var(--ink)';
        if (actor === 'clerk') actorDotColor = '#8A8A93';
        else if (actor === 'salesperson') actorDotColor = 'var(--accent)';
        else if (actor === 'accountant') actorDotColor = 'var(--warning)';
        else if (actor === 'bank') actorDotColor = 'var(--success)';

        line.innerHTML = `
            <div class="narration-dot" style="background: ${actorDotColor};"></div>
            <div class="narration-body">
                <div class="narration-title">${escapeHTML(title)}</div>
                <div class="narration-desc">${escapeHTML(caption)}</div>
            </div>
        `;

        narrationRail.appendChild(line);

        // Auto-scroll narration if near bottom
        const threshold = 120;
        const isNearBottom = narrationRail.scrollHeight - narrationRail.scrollTop - narrationRail.clientHeight < threshold;
        if (isNearBottom) {
            narrationRail.scrollTop = narrationRail.scrollHeight;
        }
    }

    function escapeHTML(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Step Handler Matrix
    function handleTheaterStep(step) {
        const payload = JSON.parse(step.payload_json || '{}');
        appendNarration(step.actor, step.title, step.caption, step.tone);

        switch (step.stage) {
            case 'intent':
                setActiveActor('buyer');
                if (actorScreens.buyer) {
                    actorScreens.buyer.innerHTML = `
                        <div class="speech-bubble">
                            <span style="font-size: 11px; text-transform: uppercase; color: var(--muted); display: block; margin-bottom: 2px;">Prompt</span>
                            &ldquo;${escapeHTML(payload.utterance)}&rdquo;
                        </div>
                    `;
                }
                break;

            case 'clerk':
                setActiveActor('clerk', 1);
                if (actorScreens.clerk) {
                    const sig = payload.signals || {};
                    actorScreens.clerk.innerHTML = `
                        <div class="card-screen-details">
                            <div class="screen-row"><span>Category</span><strong class="badge-tag tag-neutral">${escapeHTML(sig.category)}</strong></div>
                            <div class="screen-row"><span>Max Budget</span><strong class="tabular-nums">${formatINR(sig.budget_minor)}</strong></div>
                            <div class="screen-row"><span>Urgency</span><strong class="badge-tag tag-warning">${escapeHTML(sig.urgency)}</strong></div>
                        </div>
                    `;
                }
                break;

            case 'salesperson':
                setActiveActor('salesperson', selectedMode === 'race' ? 2 : 1);
                if (actorScreens.salesperson) {
                    const prop = payload.proposed || {};
                    const isLive = payload.provider === 'live';
                    actorScreens.salesperson.innerHTML = `
                        <div class="card-screen-details">
                            <div class="screen-row">
                                <span>Engine</span>
                                <span class="badge-tag ${isLive ? 'tag-accent' : 'tag-neutral'}">${escapeHTML(payload.provider)} (${payload.latency_ms}ms)</span>
                            </div>
                            <div class="screen-row"><span>Product</span><strong>${escapeHTML(prop.sku_id)}</strong></div>
                            <div class="screen-row"><span>Offer Price</span><strong class="tabular-nums" style="color: var(--accent);">${formatINR(prop.price_minor)}</strong></div>
                            <div style="font-size: 11px; color: var(--muted); margin-top: 4px; line-height: 1.3;">
                                ${escapeHTML(payload.rationale)}
                            </div>
                        </div>
                    `;
                }
                break;

            case 'offers':
                // Updates Race comparison bar if present
                if (selectedMode === 'race' && raceBar) {
                    const gOff = payload.growth_offer || {};
                    const rOff = payload.rules_offer || {};
                    document.getElementById('race-rules-title').textContent = rOff.selected_sku_id || 'SKU-01';
                    document.getElementById('race-rules-price').textContent = formatINR(rOff.proposed_price_minor);
                    document.getElementById('race-growth-title').textContent = gOff.selected_sku_id || 'SKU-01';
                    document.getElementById('race-growth-price').textContent = formatINR(gOff.proposed_price_minor);
                }
                break;

            case 'gate':
                setActiveActor('accountant', 3);
                if (actorScreens.accountant) {
                    const checks = payload.checks || [];
                    const rowsHtml = checks.map((c, idx) => `
                        <div class="gate-check-row check-${c.status}" style="animation-delay: ${idx * 120}ms;">
                            <span class="gate-check-name">${escapeHTML(c.name)}</span>
                            <span class="badge-tag ${c.status === 'pass' ? 'tag-success' : 'tag-warning'}">${c.status.toUpperCase()}</span>
                        </div>
                    `).join('');

                    actorScreens.accountant.innerHTML = `
                        <div class="card-screen-details">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-size: 11px; color: var(--muted);">CommerceProof</span>
                                <span class="badge-tag ${payload.action === 'EXECUTE' ? 'tag-success' : 'tag-warning'}">${escapeHTML(payload.action)}</span>
                            </div>
                            <div class="gate-checks-list">${rowsHtml}</div>
                        </div>
                    `;
                }
                break;

            case 'razorpay':
                setActiveActor('bank', 4);
                if (actorScreens.bank) {
                    actorScreens.bank.innerHTML = `
                        <div class="card-screen-details">
                            <div class="screen-row">
                                <span>Order ID</span>
                                <span style="font-family: var(--font-mono); font-weight: 600; color: var(--ink);">${escapeHTML(payload.order_id)}</span>
                            </div>
                            <div class="screen-row">
                                <span>Locked Amount</span>
                                <strong class="tabular-nums">${formatINR(payload.amount_minor)}</strong>
                            </div>
                            <div style="margin-top: 6px;">
                                <span class="badge-tag tag-accent">Order Authorized</span>
                            </div>
                        </div>
                    `;
                }
                break;

            case 'settle':
                setActiveActor('bank');
                if (actorScreens.bank) {
                    actorScreens.bank.innerHTML = `
                        <div class="card-screen-details">
                            <div class="screen-row">
                                <span>Payment</span>
                                <span style="font-family: var(--font-mono); font-weight: 600;">${escapeHTML(payload.payment_id)}</span>
                            </div>
                            <div class="screen-row">
                                <span>Signature</span>
                                <span class="badge-tag tag-success">HMAC-SHA256 VERIFIED</span>
                            </div>
                            <div style="margin-top: 6px;">
                                <span class="badge-tag tag-success">Captured to Ledger</span>
                            </div>
                        </div>
                    `;
                }
                break;

            case 'outcome':
                // Show outcome strip
                if (outcomeStrip) {
                    outcomeStrip.style.display = 'block';
                    const lanes = payload.lanes || [];
                    const growthLane = lanes.find(l => l.arm === 'growth') || lanes[0] || {};
                    const rulesLane = lanes.find(l => l.arm === 'rules');

                    const statusVal = document.getElementById('outcome-status-val');
                    if (statusVal) {
                        statusVal.textContent = growthLane.converted ? 'CONVERTED (PAID)' : 'DECLINED';
                        statusVal.style.color = growthLane.converted ? 'var(--success)' : 'var(--danger)';
                    }

                    animateCountUp(document.getElementById('outcome-price-val'), growthLane.final_price_minor, '', '', true);
                    animateCountUp(document.getElementById('outcome-rounds-val'), growthLane.rounds || 1);
                    animateCountUp(document.getElementById('outcome-events-val'), payload.total_events || 6, '', ' pkts');

                    const traceBtn = document.getElementById('btn-outcome-trace');
                    if (traceBtn && currentSessionId) {
                        traceBtn.href = `/dashboard/trace/${currentSessionId}`;
                    }

                    if (selectedMode === 'race') {
                        const rulesStatus = document.getElementById('race-rules-status');
                        const growthStatus = document.getElementById('race-growth-status');
                        if (rulesStatus && rulesLane) {
                            rulesStatus.innerHTML = rulesLane.converted ? '<span class="badge-tag tag-success">WON (Converted)</span>' : '<span class="badge-tag tag-danger">Lost (Declined)</span>';
                        }
                        if (growthStatus) {
                            growthStatus.innerHTML = growthLane.converted ? '<span class="badge-tag tag-success">WON (Converted)</span>' : '<span class="badge-tag tag-danger">Lost (Declined)</span>';
                        }
                    }
                }
                break;

            case 'reveal':
                if (revealBox) {
                    revealBox.style.display = 'block';
                    animateCountUp(document.getElementById('reveal-budget'), payload.true_budget_minor, '', '', true);
                    document.getElementById('reveal-price-sens').textContent = (payload.price_sensitivity || 0).toFixed(2);
                    document.getElementById('reveal-deliv-sens').textContent = (payload.delivery_sensitivity || 0).toFixed(2);
                    document.getElementById('reveal-divergence').textContent = ((payload.divergence || 0) * 100).toFixed(0) + '%';
                    document.getElementById('reveal-reason-text').textContent = payload.winner_reason || 'Evaluator assessment complete.';
                }
                break;
        }
    }

    // Run Performance Action
    async function startPerformance(random = false) {
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }

        const utterance = utteranceInput ? utteranceInput.value.trim() : '';
        const useLiveLlm = liveLlmToggle ? liveLlmToggle.checked : false;

        resetStage();

        if (statusLabel) {
            statusLabel.textContent = 'ACTING';
            statusLabel.className = 'badge-tag tag-accent';
        }
        if (liveDot) liveDot.style.display = 'inline-block';
        if (runBtn) runBtn.disabled = true;

        try {
            const resp = await fetch('/api/theater/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    utterance: utterance || null,
                    random: random,
                    mode: selectedMode,
                    use_live_llm: useLiveLlm
                })
            });

            if (!resp.ok) {
                const errJson = await resp.json().catch(() => ({}));
                throw new Error(errJson.detail || `Server returned ${resp.status}`);
            }

            const data = await resp.json();
            currentSessionId = data.session_id;

            if (random && utteranceInput && data.utterance) {
                utteranceInput.value = data.utterance;
            }

            // Connect SSE
            currentEventSource = new EventSource(`/api/theater/events?run_id=${encodeURIComponent(data.run_id)}`);

            currentEventSource.addEventListener('step', (e) => {
                try {
                    const stepData = JSON.parse(e.data);
                    handleTheaterStep(stepData);
                } catch (err) {
                    console.error('Failed to parse theater step:', err);
                }
            });

            currentEventSource.addEventListener('done', () => {
                if (currentEventSource) {
                    currentEventSource.close();
                    currentEventSource = null;
                }
                if (statusLabel) {
                    statusLabel.textContent = 'COMPLETE';
                    statusLabel.className = 'badge-tag tag-success';
                }
                if (liveDot) liveDot.style.display = 'none';
                if (runBtn) runBtn.disabled = false;

                // Mark all acting cards as done
                Object.values(actorCards).forEach(card => {
                    if (card && card.classList.contains('actor-acting')) {
                        card.classList.remove('actor-acting');
                        card.classList.add('actor-done');
                    }
                });
            });

            currentEventSource.onerror = (err) => {
                console.warn('Theater EventSource error:', err);
                if (currentEventSource) {
                    currentEventSource.close();
                    currentEventSource = null;
                }
                if (statusLabel) {
                    statusLabel.textContent = 'STANDBY';
                    statusLabel.className = 'badge-tag tag-neutral';
                }
                if (liveDot) liveDot.style.display = 'none';
                if (runBtn) runBtn.disabled = false;
            };

        } catch (err) {
            console.error('Failed to start theater performance:', err);
            appendNarration('system', 'Error Initializing Performance', err.message, 'danger');
            if (statusLabel) {
                statusLabel.textContent = 'ERROR';
                statusLabel.className = 'badge-tag tag-danger';
            }
            if (liveDot) liveDot.style.display = 'none';
            if (runBtn) runBtn.disabled = false;
        }
    }

    // Attach Listeners
    if (runBtn) {
        runBtn.addEventListener('click', () => startPerformance(false));
    }

    if (randomBtn) {
        randomBtn.addEventListener('click', () => startPerformance(true));
    }

    // Default Init
    setMode('solo');

})();
