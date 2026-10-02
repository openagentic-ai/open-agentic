"""Composition root for the commerce application, outside the Agent foundation."""

from fastapi import FastAPI


def mount_commerce(app: FastAPI) -> None:
    # Importing adapters also registers business ORM models before app startup.
    from openagentic.merchants.router import router as merchants
    from openagentic.catalog.router import router as catalog
    from openagentic.commerce.router import router as orders
    from openagentic.commerce.agent_router import router as agents
    from openagentic.commerce.operations import router as operations
    from openagentic.commerce.finance_router import router as finance
    from openagentic.commerce.support_router import router as support
    from openagentic.integrations.router import router as integrations

    @app.get("/api/commerce/capabilities", tags=["commerce"])
    async def capabilities():
        provider = getattr(app.state, "payment_provider", None)
        return {
            "application": "openagentic-commerce",
            "stage": "1.0-local-candidate",
            "milestones": {
                "0.1": [
                    "merchant_workspace",
                    "published_catalog",
                    "confirmed_booking",
                    "obsidian_memory_ui",
                ],
                "0.2": [
                    "agent_tools",
                    "quotes",
                    "delegated_grants",
                    "tool_audits",
                    "offline_qr",
                    "catalog_import",
                ],
                "1.0": [
                    "pilot_evidence",
                    "billing_policy",
                    "simulated_payment",
                    "refund",
                    "support_cases",
                    "delivery_retry",
                ],
            },
            "payment_mode": provider.mode if provider else "disabled",
            "real_money": False,
            "default_agent_mode": "local_tools",
            "model_calls": "explicit_engine_configuration_required",
        }

    for router in (merchants, catalog, orders, agents, operations, finance, support, integrations):
        app.include_router(router)
