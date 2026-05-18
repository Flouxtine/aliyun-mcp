"""Performance / monitoring hints."""

METRICS_MAPPING = {
    "ECS": {"namespace": "acs_ecs_dashboard", "cpu": "CPUUtilization", "mem": "memory_usedutilization"},
    "RDS": {"namespace": "acs_rds_dashboard", "cpu": "CpuUsage", "conn": "ConnectionUsage"},
    "SLB": {"namespace": "acs_slb_dashboard", "qps": "Qps"},
}

PERFORMANCE_THRESHOLDS = {
    "cpu_percent_warn": 75,
    "cpu_percent_crit": 90,
    "mem_percent_warn": 80,
    "mem_percent_crit": 92,
}


def register(mcp):
    @mcp.resource("aliyun://performance/metrics-mapping")
    def get_metrics_mapping() -> dict:
        """云监控 Namespace 与常用指标示意。"""
        return METRICS_MAPPING

    @mcp.resource("aliyun://performance/thresholds")
    def get_performance_thresholds() -> dict:
        """通用容量告警阈值（示意，需按业务调参）。"""
        return PERFORMANCE_THRESHOLDS
