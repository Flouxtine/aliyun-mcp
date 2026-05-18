"""Compliance prompts."""

AUDIT_TRAIL = """
你是合规审计员。请使用 `aliyun_lookup_events` 检索 ActionTrail 事件，时间范围 ISO8601 UTC，
并结合 `lookup_attributes` 过滤 ServiceName/EventName/User 等键；输出时间线与敏感操作列表，勿外泄 AK。
"""


def register(mcp):
    @mcp.prompt()
    def actiontrail_timeline() -> str:
        """ActionTrail 事件检索模板。"""
        return AUDIT_TRAIL
