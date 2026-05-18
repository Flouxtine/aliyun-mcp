"""Operations playbooks (concise)."""

TROUBLESHOOTING_PATHS = {
    "ecs_ssh": ["检查安全组入向 22", "检查 EIP/公网带宽", "检查密钥对与系统防火墙"],
    "rds_connect": ["白名单与安全组", "连接串与 SSL", "连接数与线程阻塞"],
    "slb_502": ["后端 ECS 健康检查", "监听与证书", "会话保持与超时"],
}

SEVERITY_LEVELS = {"P0": "全站不可用", "P1": "核心路径受损", "P2": "局部或可降级"}

INSPECTION_ITEMS = ["账号 MFA 与 AK 轮换", "ActionTrail 是否覆盖关键地域", "高危安全组规则", "OSS 公网访问"]

RISK_LEVELS = {"low": "可观察", "medium": "需计划处理", "high": "需立即评估"}


def register(mcp):
    @mcp.resource("aliyun://operations/troubleshooting-paths")
    def get_troubleshooting_paths() -> dict:
        """简要排障路径索引。"""
        return TROUBLESHOOTING_PATHS

    @mcp.resource("aliyun://operations/severity-levels")
    def get_severity_levels() -> dict:
        """严重级别定义。"""
        return SEVERITY_LEVELS

    @mcp.resource("aliyun://operations/inspection-items")
    def get_inspection_items() -> list:
        """巡检项示例。"""
        return INSPECTION_ITEMS

    @mcp.resource("aliyun://operations/risk-levels")
    def get_risk_levels() -> dict:
        """风险等级。"""
        return RISK_LEVELS
