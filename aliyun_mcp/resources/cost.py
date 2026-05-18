"""Cost-related hints."""

COST_OPT_BEST_PRACTICES = [
    "按量与包年包月混合：长期稳定负载优先包年，突发用按量。",
    "释放闲置 ECS 公网 IP、未挂载云盘与旧快照。",
    "使用标签与财务单元做成本分摊，结合 aliyun_query_bill_overview 对账。",
]


def register(mcp):
    @mcp.resource("aliyun://cost/best-practices")
    def get_cost_best_practices() -> list:
        """FinOps 简要最佳实践。"""
        return COST_OPT_BEST_PRACTICES
