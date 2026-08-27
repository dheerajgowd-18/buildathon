"""Multi-round negotiation state machine engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from merchantos_core.contracts import (
    AgentInput,
    NegotiationEvent,
    NegotiationSessionState,
    ProposedOffer,
    SimulatedScenario,
)
from merchantos_core.negotiation.buyer_simulator import BuyerSimulator

if TYPE_CHECKING:
    from merchantos_core.agents.growth_agent import MerchantGrowthAgent
    from merchantos_core.agents.rules_baseline import RulesBaselineAgent


class NegotiationEngine:
    """State machine engine executing multi-round commercial negotiations."""

    MAX_ROUNDS: int = 3

    def __init__(self, buyer_simulator: BuyerSimulator | None = None) -> None:
        """Initialize negotiation engine.

        Args:
            buyer_simulator: Buyer evaluation simulator (defaults to BuyerSimulator).
        """
        self.buyer_simulator: BuyerSimulator = buyer_simulator or BuyerSimulator()

    def run_session(
        self,
        scenario: SimulatedScenario,
        merchant_agent: RulesBaselineAgent | MerchantGrowthAgent,
        buyer_simulator: BuyerSimulator | None = None,
    ) -> NegotiationSessionState:
        """Execute a multi-round negotiation session between a merchant agent and buyer simulator.

        State Machine Progression:
            Round 1..MAX_ROUNDS:
              1. Build strict AgentInput (stripping ground-truth intent, including history).
              2. Merchant agent generates ProposedOffer.
              3. Log merchant NegotiationEvent.
              4. Buyer simulator evaluates offer against ground truth BuyerIntent.
              5. Log buyer NegotiationEvent (accept / reject / counter).
              6. If accept/reject -> terminate session.
              7. If counter -> update NL utterance with counter text and proceed to next round.
            If MAX_ROUNDS reached without termination -> status is 'max_rounds_reached'.

        Args:
            scenario: SimulatedScenario containing ground-truth intent, catalog, policy, and initial utterance.
            merchant_agent: RulesBaselineAgent or MerchantGrowthAgent.
            buyer_simulator: Optional custom buyer simulator.

        Returns:
            NegotiationSessionState containing final status, round count, full history, and final offer.
        """
        simulator = buyer_simulator or self.buyer_simulator
        history: list[NegotiationEvent] = []
        status: Literal["in_progress", "accepted", "rejected", "max_rounds_reached"] = "in_progress"
        final_offer: ProposedOffer | None = None
        current_utterance = scenario.nl_utterance
        last_round_executed = 0

        for round_num in range(1, self.MAX_ROUNDS + 1):
            last_round_executed = round_num

            # 1. Construct strict AgentInput (NO ground truth intent)
            agent_input = AgentInput(
                session_id=scenario.scenario_id,
                nl_utterance=current_utterance,
                available_catalog=scenario.available_catalog,
                merchant_policy=scenario.merchant_policy,
                negotiation_history=list(history),
            )

            # 2. Merchant Agent produces ProposedOffer
            offer = merchant_agent.score_and_propose(agent_input)
            final_offer = offer

            # 3. Log merchant offer event
            merchant_event = NegotiationEvent(
                session_id=scenario.scenario_id,
                round=round_num,
                actor="merchant_agent",
                message_type="initial_offer" if round_num == 1 else "counter_offer",
                offer_id=offer.offer_id,
                proposed_offer=offer,
                reason_text=offer.rationale,
            )
            history.append(merchant_event)

            # 4. Buyer simulator evaluates offer against ground truth
            buyer_response = simulator.evaluate_offer(
                offer=offer,
                intent=scenario.intent,
                catalog=scenario.available_catalog,
            )

            # 5. Process buyer response
            if buyer_response.action == "accept":
                buyer_event = NegotiationEvent(
                    session_id=scenario.scenario_id,
                    round=round_num,
                    actor="buyer_agent",
                    message_type="accept",
                    offer_id=offer.offer_id,
                    proposed_offer=offer,
                    reason_text=buyer_response.reason,
                )
                history.append(buyer_event)
                status = "accepted"
                break

            elif buyer_response.action == "reject":
                buyer_event = NegotiationEvent(
                    session_id=scenario.scenario_id,
                    round=round_num,
                    actor="buyer_agent",
                    message_type="reject",
                    offer_id=offer.offer_id,
                    proposed_offer=offer,
                    reason_text=buyer_response.reason,
                )
                history.append(buyer_event)
                status = "rejected"
                break

            else:  # counter
                buyer_event = NegotiationEvent(
                    session_id=scenario.scenario_id,
                    round=round_num,
                    actor="buyer_agent",
                    message_type="counter_offer",
                    offer_id=offer.offer_id,
                    proposed_offer=offer,
                    reason_text=buyer_response.reason,
                )
                history.append(buyer_event)
                if buyer_response.counter_utterance:
                    current_utterance = buyer_response.counter_utterance

        if status == "in_progress":
            status = "max_rounds_reached"

        return NegotiationSessionState(
            session_id=scenario.scenario_id,
            status=status,
            current_round=last_round_executed,
            history=history,
            final_offer=final_offer,
        )
