"""LLM-based Merchant Growth Agent with deterministic safety clamping."""

from __future__ import annotations

from typing import Literal

from merchantos_core.config import Settings
from merchantos_core.contracts import (
    AgentInput,
    Product,
    ProposedOffer,
)
from merchantos_core.llm.prompts import build_merchant_prompt
from merchantos_core.llm.provider import AbstractLLMProvider, MockLLMProvider


def build_llm_provider(settings: Settings) -> AbstractLLMProvider:
    """Factory to construct either Mock or real OpenAI-compatible LLM provider based on settings."""
    if settings.llm_use_mock:
        return MockLLMProvider()
    if not settings.llm_api_key or not settings.llm_api_key.get_secret_value().strip():
        raise ValueError("LLM_API_KEY is required when LLM_USE_MOCK is False")
    from merchantos_core.llm.openai_provider import OpenAICompatibleLLMProvider

    return OpenAICompatibleLLMProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model_name,
    )


class MerchantGrowthAgent:
    """LLM-driven merchant decision agent enforcing 'LLM proposes, code disposes' safety.

    This agent uses an LLM provider to reason about buyer intent and negotiate,
    but deterministically validates and clamps all generated offers to strictly
    guarantee merchant policy compliance (discount caps, margin floors, catalog existence).
    """

    def __init__(
        self,
        llm_provider: AbstractLLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the growth agent with an LLM provider or settings.

        Args:
            llm_provider: Implementation of AbstractLLMProvider (optional).
            settings: Settings instance to build provider if llm_provider is not provided.
        """
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif settings is not None:
            self.llm_provider = build_llm_provider(settings)
        else:
            self.llm_provider = MockLLMProvider()

    def score_and_propose(self, agent_input: AgentInput) -> ProposedOffer:
        """Evaluate agent input via LLM and propose a policy-clamped commercial offer.

        Strict Input Enforcement:
            Must accept AgentInput and ONLY AgentInput. Rejects SimulatedScenario,
            BuyerIntent, or any payload with extra ground-truth fields.

        Safety Topology ('LLM Proposes, Code Disposes'):
            1. Prompts LLM to select SKU, price, discount, shipping tier, and rationale.
            2. Code verifies selected SKU exists in available_catalog (falls back if hallucinated).
            3. Code mathematically clamps discount to merchant_policy.discount_cap_pct.
            4. Code mathematically clamps proposed price to merchant_policy.margin_floor_pct.
            5. Guarantees proposed_price_minor + discount_minor == base_price_minor.

        Args:
            agent_input: Validated AgentInput model.

        Returns:
            Deterministic ProposedOffer model guaranteed compliant with merchant policy.
        """
        # Strict boundary enforcement
        if not isinstance(agent_input, AgentInput):
            if hasattr(agent_input, "model_dump"):
                agent_input = AgentInput.model_validate(agent_input.model_dump())
            elif isinstance(agent_input, dict):
                agent_input = AgentInput.model_validate(agent_input)
            else:
                raise TypeError(f"Expected AgentInput instance, got {type(agent_input).__name__}")

        if not agent_input.available_catalog:
            raise ValueError("available_catalog must not be empty")

        # 1. Build prompt and query LLM provider
        system_prompt, user_prompt = build_merchant_prompt(agent_input)
        llm_output = self.llm_provider.generate_offer_proposal(system_prompt, user_prompt)

        # 2. Validate and resolve SKU (hallucination defense)
        catalog_by_sku: dict[str, Product] = {p.sku_id: p for p in agent_input.available_catalog}
        selected_product = catalog_by_sku.get(llm_output.selected_sku_id)

        sku_fallback = False
        if selected_product is None:
            sku_fallback = True
            # Fallback to cheapest catalog item (tie-break with sku_id for determinism)
            selected_product = min(agent_input.available_catalog, key=lambda p: (p.base_price_minor, p.sku_id))

        # 3. Deterministic policy enforcement ('Code Disposes')
        base_price_minor = selected_product.base_price_minor
        cost_minor = selected_product.cost_minor
        policy = agent_input.merchant_policy

        # Calculate commercial boundaries
        max_discount_cap_minor = int(base_price_minor * policy.discount_cap_pct)
        min_price_margin_minor = int(cost_minor * (1.0 + policy.margin_floor_pct))
        min_price_cap_minor = base_price_minor - max_discount_cap_minor

        # Effective minimum allowable price and maximum allowable discount
        min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)
        max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)

        # Clamp proposed discount
        raw_discount = max(0, llm_output.discount_minor)
        clamped_discount = min(raw_discount, max_allowed_discount_minor)
        clamped_price = base_price_minor - clamped_discount

        if clamped_price < min_allowed_price_minor:
            clamped_price = min_allowed_price_minor
            clamped_discount = max(0, base_price_minor - clamped_price)

        # Validate shipping tier
        shipping_tier: Literal["standard", "express"] = (
            "express" if llm_output.shipping_tier == "express" else "standard"
        )

        # Construct rationale with clamping transparency
        rationale = llm_output.rationale or "LLM proposal generated."
        notes: list[str] = []
        if sku_fallback:
            notes.append(f"Selected SKU {llm_output.selected_sku_id} not in catalog; substituted with {selected_product.sku_id}")
        if clamped_discount != raw_discount:
            notes.append(
                f"Discount clamped from ₹{raw_discount / 100:.2f} to ₹{clamped_discount / 100:.2f} "
                f"to respect merchant policy (cap={policy.discount_cap_pct * 100:.0f}%, margin_floor={policy.margin_floor_pct * 100:.0f}%)"
            )

        if notes:
            rationale = f"{rationale} [Guardrail Enforcement: {'; '.join(notes)}]"

        offer_id = f"off_{agent_input.session_id}_{selected_product.sku_id}"

        return ProposedOffer(
            offer_id=offer_id,
            session_id=agent_input.session_id,
            selected_sku_id=selected_product.sku_id,
            proposed_price_minor=clamped_price,
            discount_minor=clamped_discount,
            shipping_tier=shipping_tier,
            rationale=rationale,
        )
