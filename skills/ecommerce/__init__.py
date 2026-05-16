"""
Ecommerce skill — WooCommerce REST + Medusa.

Repo: https://github.com/medusajs/medusa
WooCommerce REST API: /wp-json/wc/v3/

Hackknow shop:  https://shop.hackknow.com
"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from core.logger import get_logger

log = get_logger("skill:ecommerce")

manifest = {
    "description": "Run WooCommerce + Medusa operations. instruction in plain English; this skill exposes raw verbs through op + payload.",
    "parameters": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["list_products", "get_product", "create_product", "update_product", "list_orders", "get_order", "low_stock"]},
            "payload": {"type": "object"},
            "instruction": {"type": "string"},
            "context": {"type": "object"},
        },
    },
}


def _wc_auth() -> tuple[str, str] | None:
    if settings.wc_consumer_key and settings.wc_consumer_secret:
        return settings.wc_consumer_key, settings.wc_consumer_secret
    return None


async def _wc(method: str, path: str, json: dict | None = None, params: dict | None = None) -> Any:
    auth = _wc_auth()
    if not auth:
        return {"status": "skipped", "reason": "WC creds missing"}
    url = f"{settings.wc_base_url}/wp-json/wc/v3{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request(method, url, auth=auth, json=json, params=params)
        r.raise_for_status()
        return r.json()


async def run(
    op: str | None = None,
    payload: dict | None = None,
    instruction: str | None = None,
    context: dict | None = None,
    **_: Any,
) -> Any:
    payload = payload or {}
    # If no explicit op, try to infer from instruction
    if not op and instruction:
        low = instruction.lower()
        if "list product" in low: op = "list_products"
        elif "create product" in low: op = "create_product"
        elif "low stock" in low: op = "low_stock"
        elif "order" in low: op = "list_orders"
    if not op:
        return {"status": "noop", "reason": "no op inferred", "instruction": instruction}

    if op == "list_products":
        return await _wc("GET", "/products", params={"per_page": payload.get("per_page", 20)})
    if op == "get_product":
        return await _wc("GET", f"/products/{payload['id']}")
    if op == "create_product":
        return await _wc("POST", "/products", json=payload)
    if op == "update_product":
        return await _wc("PUT", f"/products/{payload.pop('id')}", json=payload)
    if op == "list_orders":
        return await _wc("GET", "/orders", params={"per_page": payload.get("per_page", 20)})
    if op == "get_order":
        return await _wc("GET", f"/orders/{payload['id']}")
    if op == "low_stock":
        products = await _wc("GET", "/products", params={"stock_status": "outofstock", "per_page": 50})
        return {"out_of_stock_count": len(products), "items": products[:10] if isinstance(products, list) else products}
    return {"status": "unknown_op", "op": op}
