"""Billing read-only tools (BssOpenApi)."""
from typing import Any, Dict, Optional

from alibabacloud_bssopenapi20171214 import models as bss_models

from aliyun_mcp.config.accounts import validate_account
from aliyun_mcp.core.client_factory import get_bss_client, get_runtime_options
from aliyun_mcp.utils.serialize import openapi_response_to_dict


def register(mcp):
    def _pick(data: Dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if k in data:
                return data[k]
        return None

    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @mcp.tool()
    def aliyun_query_bill_overview(
        account: str,
        billing_cycle: str,
        region: Optional[str] = None,
        product_code: Optional[str] = None,
        product_type: Optional[str] = None,
        subscription_type: Optional[str] = None,
        bill_owner_id: Optional[int] = None,
        include_raw: bool = False,
        max_items: int = 100,
    ) -> Dict[str, Any]:
        """
        查询指定账期账单总览（QueryBillOverview，只读）。billing_cycle 格式 YYYY-MM。

        参数:
            account: 账号标识
            billing_cycle: 账期，例如 2026-04
            region: 可选，用于客户端 endpoint 区域（账单 API 常使用主账号区域）
            product_code: 可选产品代码
            product_type: 可选产品类型
            subscription_type: Subscription 或 PayAsYouGo
            bill_owner_id: 可选，财务云成员账号 ID
            include_raw: 是否附带原始响应体（默认 False）
            max_items: 返回产品明细数量上限（默认 100）
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_bss_client(account, region)
        req = bss_models.QueryBillOverviewRequest(
            billing_cycle=billing_cycle,
            product_code=product_code,
            product_type=product_type,
            subscription_type=subscription_type,
            bill_owner_id=bill_owner_id,
        )
        resp = client.query_bill_overview_with_options(req, get_runtime_options())
        payload = openapi_response_to_dict(resp)
        body = payload.get("body") if isinstance(payload, dict) else None

        if not isinstance(body, dict):
            return payload

        code = _pick(body, "Code", "code")
        message = _pick(body, "Message", "message")
        data = _pick(body, "Data", "data") or {}
        if not isinstance(data, dict):
            data = {}

        items_container = _pick(data, "Items", "items") or {}
        if isinstance(items_container, dict):
            items = _pick(items_container, "Item", "item") or []
        else:
            items = []
        if not isinstance(items, list):
            items = []

        simplified_items = []
        for item in items[: max(1, max_items)]:
            if not isinstance(item, dict):
                continue
            simplified_items.append(
                {
                    "product_name": _pick(item, "ProductName", "product_name"),
                    "product_detail": _pick(item, "ProductDetail", "product_detail"),
                    "outstanding_amount": _to_float(_pick(item, "OutstandingAmount", "outstanding_amount")),
                    "pretax_gross_amount": _to_float(_pick(item, "PretaxGrossAmount", "pretax_gross_amount")),
                    "invoice_discount": _to_float(_pick(item, "InvoiceDiscount", "invoice_discount")),
                }
            )

        result: Dict[str, Any] = {
            "account": account,
            "billing_cycle": _pick(data, "BillingCycle", "billing_cycle") or billing_cycle,
            "code": code,
            "message": message,
            "account_name": _pick(data, "AccountName", "account_name"),
            "currency": _pick(data, "Currency", "currency"),
            "totals": {
                "outstanding_amount": _to_float(_pick(data, "OutstandingAmount", "outstanding_amount")),
                "pretax_amount": _to_float(_pick(data, "PretaxAmount", "pretax_amount")),
                "pretax_gross_amount": _to_float(_pick(data, "PretaxGrossAmount", "pretax_gross_amount")),
                "invoice_discount": _to_float(_pick(data, "InvoiceDiscount", "invoice_discount")),
            },
            "item_count": len(items),
            "returned_item_count": len(simplified_items),
            "truncated": len(items) > len(simplified_items),
            "items": simplified_items,
        }

        if include_raw:
            result["raw_body"] = body

        return result
