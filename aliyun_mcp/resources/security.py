"""Security-related constants for Alibaba Cloud."""

HIGH_RISK_PORTS = {
    22: "SSH",
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
    1521: "Oracle",
    1433: "MSSQL",
    5900: "VNC",
    23: "Telnet",
}

COMPLIANCE_BASELINES = {
    "security_group": {
        "rule": "安全组禁止将高危端口对 0.0.0.0/0 暴露",
        "severity": "CRITICAL",
    },
    "oss_public_access": {
        "rule": "OSS Bucket 应关闭不必要的公读并配合 Bucket Policy",
        "severity": "HIGH",
    },
    "rds_encryption": {
        "rule": "RDS 应开启透明数据加密与 SSL 连接",
        "severity": "HIGH",
    },
    "disk_encryption": {
        "rule": "云盘与快照应使用 KMS 加密",
        "severity": "MEDIUM",
    },
    "ram_mfa": {
        "rule": "高权限 RAM 用户应强制 MFA",
        "severity": "CRITICAL",
    },
    "actiontrail": {
        "rule": "多地域投递 ActionTrail 并限制日志库访问",
        "severity": "HIGH",
    },
}


def register(mcp):
    @mcp.resource("aliyun://security/high-risk-ports")
    def get_high_risk_ports() -> dict:
        """高危端口对照表。"""
        return HIGH_RISK_PORTS

    @mcp.resource("aliyun://security/compliance-baselines")
    def get_compliance_baselines() -> dict:
        """云上合规基线（简版）。"""
        return COMPLIANCE_BASELINES
