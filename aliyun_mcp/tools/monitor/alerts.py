"""CloudMonitor read-only tools."""
from typing import Any, Dict, Optional

from alibabacloud_cms20190101 import models as cms_models

from aliyun_mcp.config.accounts import validate_account
from aliyun_mcp.core.client_factory import get_cms_client, get_runtime_options
from aliyun_mcp.utils.serialize import openapi_response_to_dict


def register(mcp):
    @mcp.tool()
    def aliyun_describe_alert_history_list(
        account: str,
        region: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        namespace: Optional[str] = None,
        metric_name: Optional[str] = None,
        rule_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        state: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        ascending: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        查询云监控告警历史（DescribeAlertHistoryList，只读）。时间戳为毫秒（Unix ms）。

        参数:
            account: 账号标识
            region: 区域，默认账号默认区域
            start_time / end_time: 毫秒时间戳字符串
            namespace / metric_name: 云产品命名空间与指标名
            rule_id / rule_name: 告警规则
            state / status: 告警状态过滤
            page / page_size: 分页
            ascending: true 为时间正序，false 为倒序
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_cms_client(account, rid)
        req = cms_models.DescribeAlertHistoryListRequest(
            region_id=rid,
            start_time=start_time,
            end_time=end_time,
            namespace=namespace,
            metric_name=metric_name,
            rule_id=rule_id,
            rule_name=rule_name,
            state=state,
            status=status,
            page=page,
            page_size=page_size,
            ascending=ascending,
        )
        resp = client.describe_alert_history_list_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)
