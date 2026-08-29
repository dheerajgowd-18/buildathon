# Panel Q&A Rehearsal Sheet (Master Plan §17)

This rehearsal guide prepares the pitch presenter for judge inquiries regarding MerchantOS AI architecture, evaluation methodology, and security boundaries.

---

## 1. Memorized North Star
> **"The LLM proposes. The policy engine disposes. No path exists from LLM output to money movement that doesn't cross deterministic validation against a bound, hashed checkout state."**

---

## 2. Core Anticipated Questions & Answers

### Q: Why Track 1 (Autonomous Agents / AI Commerce)?
**A**: Agentic commerce fundamentally alters the buyer interface. When buyers deploy autonomous agents to discover and bargain, merchants cannot rely on static catalog prices or manual negotiation desks. MerchantOS AI solves the merchant-side economic challenge that buyer AI creates.

### Q: Why AI, provably? Why not just write better rules?
**A**: The paired divergence benchmark proves this empirically. When buyer communication is clean and unambiguous (Low Divergence `<0.3`), static rules match AI performance (83.3% conversion) at zero LLM inference cost. But as buyer language diverges from underlying constraints (implicit urgency, noisy budget hints, category mismatches), the Merchant Growth Agent delivers a **+26.3% to +38.5% conversion lift**. It is a measured empirical curve, not an unsubstantiated marketing claim.

### Q: Did both agent arms see the exact same information?
**A**: Yes, deliberately and strictly. Ground-truth buyer preferences (`BuyerIntent`) never reach either agent. Both `RulesBaselineAgent` and `MerchantGrowthAgent` receive the exact same lossy natural-language input (`AgentInput`) and merchant commercial policy. All deltas isolate pure bargaining intelligence.

### Q: Didn't you just over-tune your agent on the test set?
**A**: No. The evaluation is strictly partitioned into a 100-scenario Development Split and a 50-scenario unseen Held-Out Split. The benchmark dataset was frozen prior to final execution at a tagged commit (`v1.0.0-submission-freeze`), and the exact commit hash is cited in `EVALUATION.md`. The conversion advantage holds across both splits (+19.0% on Dev, +26.0% on Held-Out).

### Q: Is your simulator biased toward your AI?
**A**: We actively enforce hermetic isolation through automated zero-leakage scans (`data/leakage_proof.json` proves 0 field leaks across 150 scenarios), paired identical-condition runs, and transparently disclosed limitations in `EVALUATION.md`. The direction of advantage consistently replicates on the held-out split.

### Q: What happens when the agent hallucinates or makes a mistake?
**A**: The deterministic `CommerceProof` control gate intercepts every proposal. Out-of-catalog SKUs and out-of-stock items are outright blocked (5.0% - 6.0% gate rejection rate), while out-of-bounds prices are mathematically clamped to merchant margin floors (`cost * (1 + margin_floor_pct)`). We can trigger a live prompt-injection attack on the Trading Floor right now to show the real-time `REPAIR` invariant in action.

### Q: How does MerchantOS AI interact with ACP, AP2, or UCP commerce protocols?
**A**: MerchantOS AI operates on the merchant decision and governance layer *above* transport protocols. It normalizes incoming intent from any protocol adapter, runs commercial negotiation, enforces merchant invariants, and binds payment authorization via Razorpay. We complement and normalize protocol standards rather than competing with them.

### Q: What can't the demo prove?
**A**: Synthetic evaluation is not production evidence. While the paired simulation proves relative strategy superiority under controlled utility curves, real-world deployment requires live A/B traffic with real merchants and buyers. We state this unprompted in `EVALUATION.md`.

### Q: What comes next after the hackathon?
**A**: Persistent cross-session merchant learning, richer multi-attribute post-purchase intelligence (returns, loyalty tiers), and broader transport protocol adapters (ACP, AP2).
