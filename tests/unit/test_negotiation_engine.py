"""Unit tests for NegotiationEngine state machine and fair boundary isolation."""

from __future__ import annotations

import pytest
from merchantos_core.agents.growth_agent import MerchantGrowthAgent
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.contracts import (
    AgentInput,
    BuyerIntent,
    BuyerResponse,
    MerchantPolicy,
    Product,
    ProposedOffer,
    SimulatedScenario,
)
from merchantos_core.negotiation.buyer_simulator import BuyerSimulator
from merchantos_core.negotiation.engine import NegotiationEngine


@pytest.fixture
def sample_catalog() -> list[Product]:
    return [
        Product(
            sku_id="SKU-LAP-001",
            name="Apex Ultrabook 14",
            category="laptops",
            cost_minor=3000000,
            base_price_minor=4000000,
            inventory_count=10,
        ),
    ]


@pytest.fixture
def sample_policy() -> MerchantPolicy:
    return MerchantPolicy(
        merchant_id="merch_001",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )


@pytest.fixture
def sample_scenario(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> SimulatedScenario:
    intent = BuyerIntent(
        session_id="sess_neg_01",
        category="laptops",
        budget_max_minor=4000000,
        delivery_days_max=2,
        priority=["performance"],
        hard_exclusions=[],
        price_sensitivity=0.6,
        delivery_sensitivity=0.2,
        acceptance_threshold=0.70,
        stated_vs_true_divergence=0.0,
    )
    return SimulatedScenario(
        scenario_id="scen_neg_01",
        intent=intent,
        nl_utterance="Looking for a laptop with budget 40k",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )


def test_negotiation_accepts_first_round(
    sample_scenario: SimulatedScenario,
) -> None:
    """When buyer simulator accepts offer on round 1, session ends with status 'accepted' and 2 events."""
    engine = NegotiationEngine()
    agent = RulesBaselineAgent()

    session_state = engine.run_session(sample_scenario, agent)

    assert session_state.status == "accepted"
    assert session_state.current_round == 1
    assert len(session_state.history) == 2
    assert session_state.history[0].actor == "merchant_agent"
    assert session_state.history[0].message_type == "initial_offer"
    assert session_state.history[1].actor == "buyer_agent"
    assert session_state.history[1].message_type == "accept"
    assert session_state.final_offer is not None


def test_negotiation_max_rounds_enforced(
    sample_scenario: SimulatedScenario,
) -> None:
    """When buyer continuously counters, engine terminates after exactly MAX_ROUNDS (3) with 'max_rounds_reached'."""
    # Create a mock buyer simulator that always counters
    class AlwaysCounterSimulator(BuyerSimulator):
        def evaluate_offer(self, offer: ProposedOffer, intent: BuyerIntent, catalog: list[Product]) -> BuyerResponse:
            return BuyerResponse(
                action="counter",
                reason="Need a lower price.",
                counter_utterance="Can you do better on the price?",
            )

    engine = NegotiationEngine(buyer_simulator=AlwaysCounterSimulator())
    agent = RulesBaselineAgent()

    session_state = engine.run_session(sample_scenario, agent)

    assert session_state.status == "max_rounds_reached"
    assert session_state.current_round == 3
    # 3 rounds * 2 events per round = 6 events
    assert len(session_state.history) == 6

    # Verify event sequencing
    assert session_state.history[0].actor == "merchant_agent"
    assert session_state.history[0].message_type == "initial_offer"
    assert session_state.history[1].actor == "buyer_agent"
    assert session_state.history[1].message_type == "counter_offer"

    assert session_state.history[2].actor == "merchant_agent"
    assert session_state.history[2].message_type == "counter_offer"
    assert session_state.history[3].actor == "buyer_agent"
    assert session_state.history[3].message_type == "counter_offer"

    assert session_state.history[4].actor == "merchant_agent"
    assert session_state.history[4].message_type == "counter_offer"
    assert session_state.history[5].actor == "buyer_agent"
    assert session_state.history[5].message_type == "counter_offer"


def test_negotiation_ground_truth_isolation(
    sample_scenario: SimulatedScenario,
) -> None:
    """Spy on merchant agent input during negotiation to assert ground-truth BuyerIntent is never passed."""
    captured_inputs: list[AgentInput] = []

    class SpyingAgent(RulesBaselineAgent):
        def score_and_propose(self, agent_input: AgentInput) -> ProposedOffer:
            captured_inputs.append(agent_input)
            return super().score_and_propose(agent_input)

    engine = NegotiationEngine()
    spying_agent = SpyingAgent()

    engine.run_session(sample_scenario, spying_agent)

    assert len(captured_inputs) >= 1
    for inp in captured_inputs:
        assert isinstance(inp, AgentInput)
        # Verify no ground-truth fields exist on AgentInput
        assert not hasattr(inp, "intent")
        assert not hasattr(inp, "budget_max_minor")
        assert not hasattr(inp, "price_sensitivity")
        assert not hasattr(inp, "acceptance_threshold")
        # Ensure negotiation history is provided
        assert isinstance(inp.negotiation_history, list)


def test_negotiation_with_growth_agent(
    sample_scenario: SimulatedScenario,
) -> None:
    """Verify NegotiationEngine runs successfully with MerchantGrowthAgent."""
    engine = NegotiationEngine()
    agent = MerchantGrowthAgent()

    session_state = engine.run_session(sample_scenario, agent)

    assert session_state.status in ("accepted", "rejected", "max_rounds_reached")
    assert len(session_state.history) >= 2
    assert session_state.final_offer is not None
    assert session_state.final_offer.proposed_price_minor + session_state.final_offer.discount_minor == 4000000
