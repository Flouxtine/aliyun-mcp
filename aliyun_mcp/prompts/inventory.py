"""Inventory prompts."""

RESOURCE_INVENTORY = """
你是资产管理员。请为项目 {project_tag} 生成阿里云资源清单：
1. 使用 `aliyun_list_tag_resources`，传入 tags 参数为 JSON 数组字符串，筛选该项目的标签键值（与你们标签规范一致）。
2. 对关键资源补充只读详情：对 ECS 调用 `aliyun_describe_instances`，对 VPC 调用 `aliyun_describe_vpcs`。
3. 输出 Markdown：先统计数量，再按产品分类列出实例 ID、VPC、区域等字段；不要臆造未返回的数据。
"""

NETWORK_TOPOLOGY = """
你是网络架构师。请基于 `aliyun_describe_vpcs` 与 `aliyun_describe_instances` 的返回，总结 {region} 的 VPC 与计算资源分布，
并给出 Mermaid 拓扑草图（仅使用工具返回中的 ID 与网段，勿编造）。
"""


def register(mcp):
    @mcp.prompt()
    def resource_inventory(project_tag: str, region: str = "cn-hangzhou") -> str:
        """生成按标签过滤的阿里云资源清单。"""
        return RESOURCE_INVENTORY.format(project_tag=project_tag, region=region)

    @mcp.prompt()
    def network_topology_sketch(region: str = "cn-hangzhou") -> str:
        """基于 DescribeVpcs/DescribeInstances 画简要拓扑。"""
        return NETWORK_TOPOLOGY.format(region=region)
