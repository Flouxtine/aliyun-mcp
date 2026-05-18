"""Monitoring prompts."""

ALERT_REVIEW = """
你是监控值班员。请调用 `aliyun_describe_alert_history_list`，结合给定时间窗（毫秒时间戳）复盘告警风暴，
输出按规则聚合的触发次数、持续区间与可能根因假设（需标注为假设并建议下一步只读查询）。
"""


def register(mcp):
    @mcp.prompt()
    def alert_history_review() -> str:
        """复盘云监控告警历史。"""
        return ALERT_REVIEW
