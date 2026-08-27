"""Prompt templates and builder for Merchant Growth Agent."""

from __future__ import annotations

import json
from merchantos_core.contracts import AgentInput


def build_merchant_prompt(agent_input: AgentInput) -> tuple[str, str]:
    """Build system and user prompts for the Merchant Growth Agent.

    Args:
        agent_input: Validated AgentInput model.

    Returns:
        tuple of (system_prompt, user_prompt).
    """
    system_prompt = (
        "You are an expert AI sales and pricing agent for an e-commerce merchant.\n"
        "Your task is to analyze the buyer's natural language utterance, past negotiation history, "
        "and available catalog to propose the best commercial offer (selected SKU, price, discount, shipping tier).\n\n"
        "STRICT REQUIREMENTS:\n"
        "1. You MUST return ONLY a valid, raw JSON object matching this schema:\n"
        "   {\n"
        '     "selected_sku_id": "<exact SKU ID from catalog>",\n'
        '     "proposed_price_minor": <integer paise>,\n'
        '     "discount_minor": <integer paise>,\n'
        '     "shipping_tier": "standard" | "express",\n'
        '     "rationale": "<concise explanation>"\n'
        "   }\n"
        "2. Do NOT output any markdown fences (```json), commentary, or extra text outside the JSON object.\n"
        "3. You are STRICTLY FORBIDDEN from hallucinating SKUs. You must pick exactly one SKU ID from the available catalog.\n"
        "4. Commercial constraints:\n"
        "   - proposed_price_minor + discount_minor MUST equal the selected product's base_price_minor.\n"
        "   - discount_minor must NOT exceed the merchant discount cap.\n"
        "   - proposed_price_minor must NOT fall below the merchant margin floor.\n"
    )

    catalog_lines = []
    for item in agent_input.available_catalog:
        catalog_lines.append(
            f"- SKU: {item.sku_id} | Name: {item.name} | Category: {item.category} | "
            f"Base Price: ₹{item.base_price_minor / 100:.2f} ({item.base_price_minor} paise) | "
            f"Cost: ₹{item.cost_minor / 100:.2f} ({item.cost_minor} paise) | Stock: {item.inventory_count}"
        )
    catalog_str = "\n".join(catalog_lines)

    policy = agent_input.merchant_policy
    policy_str = (
        f"Margin Floor: {policy.margin_floor_pct * 100:.1f}%\n"
        f"Discount Cap: {policy.discount_cap_pct * 100:.1f}%\n"
        f"Promotion Budget: ₹{policy.promotion_budget_minor / 100:.2f}"
    )

    history_lines = []
    if agent_input.negotiation_history:
        for ev in agent_input.negotiation_history:
            history_lines.append(
                f"[Round {ev.round}] Actor: {ev.actor} | Type: {ev.message_type} | "
                f"Offer ID: {ev.offer_id or 'None'} | Reason/Text: {ev.reason_text}"
            )
        history_str = "\n".join(history_lines)
    else:
        history_str = "No prior negotiation history (initial round)."

    user_prompt = (
        f"SESSION ID: {agent_input.session_id}\n\n"
        f"BUYER UTTERANCE:\n\"{agent_input.nl_utterance}\"\n\n"
        f"NEGOTIATION HISTORY:\n{history_str}\n\n"
        f"MERCHANT POLICY:\n{policy_str}\n\n"
        f"AVAILABLE CATALOG:\n{catalog_str}\n\n"
        "Generate the optimal commercial offer in valid JSON format."
    )

    return system_prompt, user_prompt
