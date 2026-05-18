"""Common Alibaba Cloud region metadata (public regions, illustrative)."""

REGIONS = [
    {"code": "cn-hangzhou", "name": "华东1（杭州）", "continent": "中国"},
    {"code": "cn-shanghai", "name": "华东2（上海）", "continent": "中国"},
    {"code": "cn-beijing", "name": "华北2（北京）", "continent": "中国"},
    {"code": "cn-shenzhen", "name": "华南1（深圳）", "continent": "中国"},
    {"code": "cn-zhangjiakou", "name": "华北3（张家口）", "continent": "中国"},
    {"code": "cn-hongkong", "name": "中国（香港）", "continent": "亚太"},
    {"code": "ap-southeast-1", "name": "新加坡", "continent": "亚太"},
    {"code": "ap-northeast-1", "name": "日本（东京）", "continent": "亚太"},
    {"code": "eu-central-1", "name": "德国（法兰克福）", "continent": "欧洲"},
    {"code": "us-east-1", "name": "美国（弗吉尼亚）", "continent": "北美"},
]

# ECS 规格族（与 AWS 分类对齐的简化说明）
INSTANCE_FAMILIES = {
    "general_purpose": {
        "name": "通用型",
        "examples": ["ecs.g7", "ecs.c7", "ecs.r7"],
        "description": "计算与内存比例均衡，适合大多数 Web 与应用服务。",
    },
    "compute_optimized": {
        "name": "计算优化",
        "examples": ["ecs.c7", "ecs.ic5"],
        "description": "更高 CPU 配比，适合计算密集场景。",
    },
    "memory_optimized": {
        "name": "内存优化",
        "examples": ["ecs.r7", "ecs.re6p"],
        "description": "更大内存，适合缓存与内存型数据库。",
    },
}


def register(mcp):
    @mcp.resource("aliyun://regions")
    def get_regions() -> list:
        """阿里云常用区域列表（代码/名称/地理分区）。"""
        return REGIONS

    @mcp.resource("aliyun://instance-families")
    def get_instance_families() -> dict:
        """ECS 规格族简要说明。"""
        return INSTANCE_FAMILIES
