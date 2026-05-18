"""Troubleshooting prompts."""

ECS_SSH = """
排查 ECS SSH 不通：先调用 `aliyun_describe_instances` 确认实例状态、VPC、交换机与绑定安全组，
再调用 `aliyun_describe_security_group_attribute` 检查入向 22 端口规则，结合 EIP/带宽与系统防火墙逐项判断；
仅基于工具结果给出结论。
"""

RDS_CONNECT = """
排查 RDS 连接：先调用 `aliyun_describe_rds_instances` 或 `aliyun_describe_rds_instance_attribute` 确认实例状态、引擎、网络类型、连接地址与端口，
再结合白名单、安全组、SSL 与 `aliyun_lookup_events` 的近期变更事件判断根因；仅基于工具结果给出结论。
"""

SLB_502 = """
排查 SLB/CLB 502 或后端不健康：先调用 `aliyun_describe_load_balancers` 确认实例状态，
再调用 `aliyun_describe_load_balancer_attribute` 查看实例详情与后端服务器，调用 `aliyun_describe_load_balancer_listeners` 查看监听配置，
最后用 `aliyun_describe_slb_health_status` 检查监听端口的后端健康状态，结合后端 ECS 安全组、服务端口与最近变更事件给出结论。
"""


def register(mcp):
    @mcp.prompt()
    def ecs_ssh_troubleshoot() -> str:
        """ECS SSH 排障思路。"""
        return ECS_SSH

    @mcp.prompt()
    def rds_connect_troubleshoot() -> str:
        """RDS 连接排障思路。"""
        return RDS_CONNECT

    @mcp.prompt()
    def slb_502_troubleshoot() -> str:
        """SLB 502/后端不健康排障思路。"""
        return SLB_502
