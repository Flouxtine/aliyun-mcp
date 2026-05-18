"""ActionTrail read-only tools."""
from typing import Any, Dict, List, Optional

from alibabacloud_actiontrail20200706 import models as at_models

from aliyun_mcp.config.accounts import validate_account
from aliyun_mcp.core.client_factory import get_actiontrail_client, get_runtime_options
from aliyun_mcp.utils.serialize import openapi_response_to_dict


def register(mcp):
    @mcp.tool()
    def aliyun_lookup_events(
        account: str,
        region: Optional[str] = None,
        lookup_attributes: Optional[List[Dict[str, str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: str = "20",
        next_token: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        检索操作审计事件（LookupEvents，只读）。lookup_attributes 每项含 key/value，
        每次请求仅支持一组条件键语义下的组合（详见 ActionTrail 文档）。

        参数:
            account: 账号标识
            region: 区域，默认账号默认区域
            lookup_attributes: 例如 [{"key":"ServiceName","value":"Ecs"}]（key 大小写以 API 为准）
            start_time / end_time: ISO8601 UTC，如 2026-05-01T00:00:00Z
            max_results: 字符串数字，0-50
            next_token: 分页
            direction: FORWARD 或 BACKWARD
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_actiontrail_client(account, region)
        attrs = None
        if lookup_attributes:
            attrs = []
            for item in lookup_attributes:
                k = item.get("key") or item.get("Key")
                v = item.get("value") or item.get("Value")
                attrs.append(at_models.LookupEventsRequestLookupAttribute(key=k, value=v))
        req = at_models.LookupEventsRequest(
            lookup_attribute=attrs,
            start_time=start_time,
            end_time=end_time,
            max_results=max_results,
            next_token=next_token,
            direction=direction,
        )
        resp = client.lookup_events_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)
