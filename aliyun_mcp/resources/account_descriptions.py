"""
Per-account Markdown descriptions (edit for your organization).
"""
ACCOUNT_DESCRIPTIONS: dict[str, str] = {
    "production": """# production 生产账号

## 概述

在此维护生产环境业务系统、网络分区与变更窗口说明，便于 Agent 查询前先了解边界。

## 建议字段

- 主区域与多活区域
- 核心产品：ECS、ACK、RDS、SLB、OSS、SLS
- 变更与发布策略（只读 MCP 不会执行变配）
""",
    "staging": """# staging 测试账号

用于联调与非生产验证；可标注与生产的数据隔离策略。
""",
}

ACCOUNT_DESCRIPTIONS_SUMMARY: dict[str, str] = {
    "production": "生产环境主账号，默认仅允许只读巡检与账单/监控查询。",
    "staging": "测试环境账号，用于联调与验证。",
}


def register(mcp):
    @mcp.resource("aliyun://account-descriptions")
    def get_account_descriptions() -> dict:
        """所有账号 Markdown 详细描述。"""
        return ACCOUNT_DESCRIPTIONS

    @mcp.resource("aliyun://account-description/{account_key}")
    def get_account_description(account_key: str) -> str:
        """单个账号 Markdown 描述。"""
        return ACCOUNT_DESCRIPTIONS.get(account_key, f"# 未找到\n\n账号 `{account_key}` 无描述，可在 account_descriptions.py 中补充。")

    @mcp.resource("aliyun://account-description/{account_key}/summary")
    def get_account_description_summary(account_key: str) -> str:
        """单个账号一句话摘要。"""
        return ACCOUNT_DESCRIPTIONS_SUMMARY.get(account_key, f"未找到账号 `{account_key}` 的摘要")
