# MerchantOS AI

> **"When the buyer becomes an AI, the merchant needs an AI that negotiates for value under a deterministic constraint gate."**

MerchantOS AI is an agentic merchant intelligence and commerce platform designed to negotiate autonomously with buyer agents, maximize conversion and contribution margin, and enforce zero-defect commercial safety.

---

## 1. The Core Architecture

> **"LLM Proposes, Code Disposes"** — All agentic reasoning (SKU selection, discount strategy, multi-turn concessions) is treated as untrusted commercial proposal; an immutable deterministic control gate (`CommerceProof`) mathematically clamps discounts to margin floors, validates real-time inventory, and cryptographically binds terms before any payment is authorized.

```
[Buyer Agent / User] <---> [Merchant Growth Agent (LLM)] ---> [ProposedOffer]
                                                                     |
                                                                     v
                                                            [CommerceProof Gate]
                                                       (Deterministic Clamping & Hash)
                                                                     |
                                                                     v
                                                         [Razorpay Payment Capture]
```

---

## 2. The Evidence: The Divergence Thesis

In paired benchmark evaluations across 150 calibrated scenarios (`dev` and `heldout`), the empirical findings prove:

1. **Low Divergence (`< 0.3`)**: When buyer natural language is simple and direct, static rules match or slightly outperform adaptive agents (83.3% vs 80.6% on Dev) at zero LLM inference cost.
2. **Medium & High Divergence (`>= 0.3`)**: When buyer stated preferences diverge from true underlying utility (noisy budget hints, implicit urgency, category mismatches), the **Merchant Growth Agent achieves up to a +38.5% conversion lift on medium divergence and +26.3% conversion lift on high divergence**.
3. **Load-Bearing Safety**: Across all 150 scenarios, `CommerceProof` maintained a **5.0% - 6.0% Gate Rejection Rate** (blocking unlisted or out-of-stock items) and **3.0% - 5.0% Repair Rate** (clamping out-of-bounds discounts), guaranteeing **zero margin floor breaches**.

---

## 3. Quickstart

### Prerequisites
- Python 3.11+ (or Python 3.10+)
- Standard virtual environment tools

### 1. Installation
```bash
# Clone and enter directory
cd merchantos-ai

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (including FastAPI, Jinja2, Pytest)
pip install -e ".[dev]"
```

### 2. Run All Automated Tests (116 Tests)
```bash
# Run unit, integration, adversarial, and dashboard test suites
pytest -v
```

### 3. Run Benchmark Evaluation Engine
```bash
# Run paired evaluation on 100-scenario dev split
python scripts/run_evaluation.py --dataset dev

# Run paired evaluation on 50-scenario heldout split
python scripts/run_evaluation.py --dataset heldout
```

### 4. Launch the Judge Dashboard & API Server
```bash
# Start FastAPI application
uvicorn merchantos_api.main:app --reload --port 8000
```
Open your browser and navigate to:
- **Static Judge Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard) (or `http://localhost:8000/`)
- **API Health Check**: [http://localhost:8000/healthz](http://localhost:8000/healthz)

---

## 4. Repository Structure & Documentation Map

- [`ARCHITECTURE.md`](ARCHITECTURE.md): Component topology, trust boundaries, and multi-turn sequence diagrams.
- [`EVALUATION.md`](EVALUATION.md): Paired benchmark design, divergence bucketing, and empirical results.
- [`SECURITY.md`](SECURITY.md): Defense-in-depth, prompt injection neutralization, cart mutation defense, and leakage prevention.
- [`DEMO.md`](DEMO.md): Step-by-step 5-minute judge demo script with adversarial triggers.
