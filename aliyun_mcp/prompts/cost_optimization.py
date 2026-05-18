"""Cost prompts."""

COST_ANALYSIS = """
你是 FinOps 助手。请调用 `aliyun_query_bill_overview`，对账期 {billing_cycle} 做产品维度成本拆解，
说明主要产品线占比与可优化方向；仅引用接口返回数据。注意：**每次工具调用都必须传入 `account` 参数**。
"""


def register(mcp):
    @mcp.prompt()
    def cost_overview_analysis(billing_cycle: str) -> str:
        """按账期分析账单总览。"""
        return COST_ANALYSIS.format(billing_cycle=billing_cycle)
