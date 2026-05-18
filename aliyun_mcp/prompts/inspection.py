"""Inspection prompts."""

DAILY_CHECK = """
日常巡检：1) `aliyun_describe_instances` 抽样检查状态；2) `aliyun_describe_vpcs` 核对网段；
3) `aliyun_query_bill_overview` 看异常突增；4) `aliyun_lookup_events` 关注 Write 类高危 API。
输出检查表与发现项。
"""


def register(mcp):
    @mcp.prompt()
    def daily_inspection() -> str:
        """日常巡检提示。"""
        return DAILY_CHECK
