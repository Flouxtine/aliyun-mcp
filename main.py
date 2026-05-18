"""
Alibaba Cloud multi-account MCP entrypoint.

Transports:
- stdio: local agents (Cursor, Claude Code, etc.)
- http: remote SSE clients
"""
import argparse
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from aliyun_mcp.config.accounts import (
    get_account_config,
    get_all_accounts,
    list_accounts,
    reload_accounts,
    validate_account,
)
from aliyun_mcp.prompts import register_all as register_all_prompts
from aliyun_mcp.resources import register as register_resources
from aliyun_mcp.resources.account_descriptions import ACCOUNT_DESCRIPTIONS, ACCOUNT_DESCRIPTIONS_SUMMARY
from aliyun_mcp.tools import register_all as register_all_tools
from aliyun_mcp.tools.resource.read import _get_region
from aliyun_mcp.core.client_factory import (
    get_ecs_client,
    get_kvstore_client,
    get_rds_client,
    get_runtime_options,
)
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_r_kvstore20150101 import models as kv_models
from alibabacloud_rds20140815 import models as rds_models

PRODUCT_CAPABILITY_MATRIX = {
    "ecs": {
        "enabled": True,
        "aliases": ["ecs", "云服务器", "云主机", "instance"],
        "tools": ["aliyun_describe_instances"],
    },
    "vpc": {
        "enabled": True,
        "aliases": ["vpc", "专有网络", "网络"],
        "tools": ["aliyun_describe_vpcs", "aliyun_describe_route_tables", "aliyun_describe_route_entries"],
    },
    "rds": {
        "enabled": True,
        "aliases": ["rds", "数据库"],
        "tools": ["aliyun_describe_rds_instances", "aliyun_describe_rds_instance_attribute"],
    },
    "redis": {
        "enabled": True,
        "aliases": ["redis", "tair", "kvstore"],
        "tools": ["aliyun_describe_redis_instances", "aliyun_describe_redis_instance_attribute"],
    },
    "mongodb": {
        "enabled": True,
        "aliases": ["mongodb", "dds", "mongo"],
        "tools": ["aliyun_describe_mongodb_instances", "aliyun_describe_mongodb_instance_attribute"],
    },
    "clb": {
        "enabled": True,
        "aliases": ["clb", "slb", "负载均衡"],
        "tools": [
            "aliyun_describe_load_balancers",
            "aliyun_describe_load_balancer_attribute",
            "aliyun_describe_load_balancer_listeners",
            "aliyun_describe_slb_health_status",
        ],
    },
    "alb": {
        "enabled": True,
        "aliases": ["alb"],
        "tools": ["aliyun_list_alb_load_balancers", "aliyun_get_alb_load_balancer_attribute", "aliyun_list_alb_listeners"],
    },
    "nlb": {
        "enabled": True,
        "aliases": ["nlb"],
        "tools": ["aliyun_list_nlb_load_balancers", "aliyun_get_nlb_load_balancer_attribute", "aliyun_list_nlb_listeners"],
    },
    "oss": {
        "enabled": True,
        "aliases": ["oss", "对象存储", "bucket"],
        "tools": ["aliyun_list_oss_buckets", "aliyun_get_oss_bucket_info"],
    },
    "sls": {
        "enabled": True,
        "aliases": ["sls", "日志服务", "log service", "日志"],
        "tools": ["aliyun_list_sls_projects", "aliyun_list_sls_logstores"],
    },
    "ack": {
        "enabled": True,
        "aliases": ["ack", "kubernetes", "容器服务", "k8s"],
        "tools": ["aliyun_describe_ack_clusters"],
    },
    "billing": {
        "enabled": True,
        "aliases": ["账单", "bill", "billing", "费用"],
        "tools": ["aliyun_query_bill_overview"],
    },
    "monitor": {
        "enabled": True,
        "aliases": ["监控", "cms", "告警", "alert"],
        "tools": ["aliyun_describe_alert_history_list"],
    },
    "actiontrail": {
        "enabled": True,
        "aliases": ["actiontrail", "审计", "事件"],
        "tools": ["aliyun_lookup_events"],
    },
    "elasticsearch": {
        "enabled": False,
        "aliases": ["es", "elasticsearch", "open search", "opensearch", "elk"],
        "tools": [],
        "note": "当前 MCP 尚未接入阿里云 Elasticsearch/OpenSearch 专用查询 API。",
    },
}

INTENT_RULES: List[Dict[str, Any]] = [
    {
        "intent": "account_overview",
        "keywords": ["账号", "账户", "几个账号", "哪些账号", "account"],
        "tools": ["aliyun_get_account_count", "aliyun_list_configured_accounts", "aliyun_get_account_info"],
    },
    {
        "intent": "billing_analysis",
        "keywords": ["账单", "费用", "成本", "花费", "billing", "bill", "cost"],
        "tools": ["aliyun_query_bill_overview"],
    },
    {
        "intent": "monitoring_alerts",
        "keywords": ["告警", "监控", "报警", "alert", "cms"],
        "tools": ["aliyun_describe_alert_history_list"],
    },
    {
        "intent": "audit_events",
        "keywords": ["审计", "谁改了", "变更", "事件", "actiontrail", "操作记录"],
        "tools": ["aliyun_lookup_events"],
    },
    {
        "intent": "compute_resources",
        "keywords": ["ecs", "实例", "云服务器", "主机", "资源", "有哪些资源", "各类资源", "资源概览"],
        "tools": ["aliyun_get_account_resource_snapshot", "aliyun_describe_instances"],
    },
    {
        "intent": "network_resources",
        "keywords": ["vpc", "路由", "nat", "eip", "网关", "网络"],
        "tools": [
            "aliyun_describe_vpcs",
            "aliyun_describe_route_tables",
            "aliyun_describe_route_entries",
            "aliyun_describe_nat_gateways",
            "aliyun_describe_eip_addresses",
        ],
    },
    {
        "intent": "database_resources",
        "keywords": ["rds", "redis", "tair", "mongodb", "dds", "数据库"],
        "tools": [
            "aliyun_describe_rds_instances",
            "aliyun_describe_redis_instances",
            "aliyun_describe_mongodb_instances",
        ],
    },
    {
        "intent": "loadbalancer_resources",
        "keywords": ["clb", "slb", "alb", "nlb", "负载均衡"],
        "tools": ["aliyun_describe_load_balancers", "aliyun_list_alb_load_balancers", "aliyun_list_nlb_load_balancers"],
    },
    {
        "intent": "storage_logs_resources",
        "keywords": ["oss", "bucket", "对象存储", "sls", "logstore", "日志服务"],
        "tools": ["aliyun_list_oss_buckets", "aliyun_list_sls_projects", "aliyun_list_sls_logstores"],
    },
    {
        "intent": "product_support_check",
        "keywords": ["支持", "产品", "es", "elasticsearch", "opensearch", "有没有"],
        "tools": ["aliyun_get_product_support_status", "aliyun_list_supported_products"],
    },
]


def _normalize_product_key(product: str) -> str:
    raw = product.strip().lower()
    if not raw:
        return raw

    for key, meta in PRODUCT_CAPABILITY_MATRIX.items():
        if raw == key:
            return key
        for alias in meta.get("aliases", []):
            if raw == alias.lower():
                return key
    return raw


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _detect_account_from_text(text: str) -> Optional[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    try:
        for key in list_accounts():
            if key.lower() in normalized:
                return key
    except Exception:
        return None
    return None

INSTRUCTIONS = """
你是阿里云运维助手，帮助用户在多账号环境下完成只读查询与排障。

## 执行方式（强制）

1. **仅使用 MCP 工具**：默认且必须通过本服务提供的 MCP tools 完成查询。
2. **禁止终端命令**：禁止建议或执行 terminal/shell/CLI 命令（包括 `aliyun ...`、`bash -c`、`python -c`、管道到解释器等）。
3. **禁止外部脚本解析**：不要让用户把工具结果导出到本地文件再二次脚本处理。
4. **工具不足时处理**：若现有工具无法满足请求，直接说明受限点并给出可用工具内的替代方案。
5. **产品支持性问题**：用户询问“是否支持某产品（如 ES）”时，先调用 `aliyun_get_product_support_status`，不得凭空判断。
6. **禁止读取宿主本地配置文件**：不得通过 read_file/terminal 等方式读取 `~/.hermes/*`、`~/.config/*`、`~/.aliyun/*` 等宿主文件来回答账号数量或能力问题。
7. **账号数量问题固定流程**：用户问“有几个阿里云账号/有哪些账号”时，必须先调用 `aliyun_get_account_count` 或 `aliyun_list_configured_accounts`。
8. **连接异常处理**：如发现工具不可用或服务未连接，必须调用 `aliyun_healthcheck` 或提示“请重连 MCP 服务”，不得退回本地命令。
9. **会话首轮引导**：每个新会话第一条用户请求，优先调用 `aliyun_bootstrap_session` 获取账号、能力和策略摘要后再回答。
10. **自然语言自动路由**：用户给出自然语言问题时，先调用 `aliyun_route_query_intent` 生成推荐工具，再执行查询。

## 操作原则

1. **账号背景优先**: 用户提到账号标识时，先调用 `aliyun_get_account_info(account_key=...)` 了解背景再执行其他工具。
2. **强制指定账号**: 所有资源类调用必须带 `account` 参数，避免串账号。
3. **只读**: 本 MCP 仅封装 Describe/List/Get/Lookup/Query 等只读接口，不执行变配。
4. **数据驱动**: 基于工具返回结果回答，不要臆造资源 ID 或账单金额。
5. **安全与执行约束**: 禁止输出 AK/SK/Token 等敏感信息；基于工具原始返回字段直接给出结论与摘要。

## 常用工具

- `aliyun_list_configured_accounts()`：列出已配置账号
- `aliyun_get_account_count()`：返回已配置账号数量与账号标识列表
- `aliyun_get_account_info(account_key)`：账号说明与默认区域
- `aliyun_describe_instances` / `aliyun_describe_vpcs`：ECS / VPC
- `aliyun_describe_rds_instances` / `aliyun_describe_rds_instance_attribute`：RDS 实例列表与详情
- `aliyun_describe_redis_instances` / `aliyun_describe_redis_instance_attribute`：Redis/Tair 实例列表与详情
- `aliyun_describe_mongodb_instances` / `aliyun_describe_mongodb_instance_attribute`：MongoDB 实例列表与详情
- `aliyun_describe_security_groups` / `aliyun_describe_security_group_attribute`：安全组列表与规则详情
- `aliyun_describe_load_balancers` / `aliyun_describe_load_balancer_attribute`：CLB 列表与实例详情
- `aliyun_describe_load_balancer_listeners` / `aliyun_describe_slb_health_status`：CLB 监听配置与健康状态
- `aliyun_list_alb_load_balancers` / `aliyun_get_alb_load_balancer_attribute` / `aliyun_list_alb_listeners`：ALB 列表、详情与监听
- `aliyun_list_nlb_load_balancers` / `aliyun_get_nlb_load_balancer_attribute` / `aliyun_list_nlb_listeners`：NLB 列表、详情与监听
- `aliyun_describe_eip_addresses` / `aliyun_describe_nat_gateways` / `aliyun_describe_route_tables` / `aliyun_describe_route_entries`：EIP、NAT 与路由查询
- `aliyun_describe_ack_clusters`：ACK 集群列表
- `aliyun_list_oss_buckets` / `aliyun_get_oss_bucket_info`：OSS Bucket 列表与信息
- `aliyun_list_sls_projects` / `aliyun_list_sls_logstores`：SLS Project 与 Logstore 列表
- `aliyun_list_tag_resources`：按标签或 ARN 查已标签资源（需 tags 或 resource_arns）
- `aliyun_list_support_resource_types`：标签服务支持的资源类型
- `aliyun_query_bill_overview`：账期账单总览
- `aliyun_describe_alert_history_list`：云监控告警历史
- `aliyun_lookup_events`：ActionTrail 事件检索
- `aliyun_list_supported_products`：查看本 MCP 已接入产品能力矩阵
- `aliyun_get_product_support_status`：查询指定产品是否已接入及可用工具
- `aliyun_healthcheck`：检查 MCP 运行状态与账号配置可读性
- `aliyun_get_runtime_policy`：返回本 MCP 的“仅工具模式”运行策略
- `aliyun_bootstrap_session`：会话入口摘要（账号、能力矩阵、运行策略、健康状态）
- `aliyun_route_query_intent`：根据用户问句自动判断应调用的工具与账号
- `aliyun_get_account_resource_snapshot`：按账号一次性返回核心资源数量摘要（减少多次调用）
"""

mcp = FastMCP(
    name="阿里云多账号管理工具",
    instructions=INSTRUCTIONS,
)

_SENSITIVE_ERROR_PATTERN = re.compile(r"access[_-]?key|secret|token|credential|password", re.IGNORECASE)


def _safe_error_message(exc: Exception, fallback: str) -> str:
    """Prevent accidental secret leakage in error payloads returned to MCP clients."""
    msg = str(exc)
    if _SENSITIVE_ERROR_PATTERN.search(msg):
        return fallback
    return msg


def _recommended_stdio_config() -> dict:
    repo_dir = Path(__file__).resolve().parent
    return {
        "command": str(repo_dir / ".venv" / "bin" / "python"),
        "args": [str(repo_dir / "main.py")],
        "envFile": str(repo_dir / ".env"),
    }

register_all_tools(mcp)


@mcp.tool()
def aliyun_list_configured_accounts() -> dict:
    """列出所有已配置的阿里云账号（不含密钥）。"""
    try:
        accounts = get_all_accounts()
        result = []
        for account_key, account_info in accounts.items():
            account_info = dict(account_info)
            account_info.pop("description", None)
            account_info["description"] = ACCOUNT_DESCRIPTIONS_SUMMARY.get(account_key, "暂无详细描述")
            account_info["has_detailed_description"] = account_key in ACCOUNT_DESCRIPTIONS
            result.append(account_info)
        return {
            "accounts": result,
            "count": len(result),
            "message": f"已配置 {len(result)} 个阿里云账号",
        }
    except Exception as e:
        return {
            "error": _safe_error_message(e, "账号配置异常（敏感细节已隐藏）"),
            "message": "加载账号配置失败，请检查 ALIYUN_ACCOUNT_* 环境变量",
        }


@mcp.tool()
def aliyun_get_account_count() -> dict:
    """返回当前已配置阿里云账号数量及账号标识（不含任何密钥信息）。"""
    try:
        account_keys = list_accounts()
        return {
            "count": len(account_keys),
            "account_keys": account_keys,
            "message": f"当前已配置 {len(account_keys)} 个阿里云账号",
        }
    except Exception as e:
        return {
            "error": _safe_error_message(e, "账号配置异常（敏感细节已隐藏）"),
            "message": "统计账号数量失败，请检查 ALIYUN_ACCOUNT_* 环境变量",
        }


@mcp.tool()
def aliyun_reload_account_configs() -> dict:
    """重新从环境变量加载账号配置并清理 SDK 客户端缓存。"""
    try:
        reload_accounts()
        accounts = list_accounts()
        return {
            "success": True,
            "accounts": accounts,
            "message": f"账号配置已重新加载，共 {len(accounts)} 个账号",
        }
    except Exception as e:
        return {
            "success": False,
            "error": _safe_error_message(e, "账号配置异常（敏感细节已隐藏）"),
            "message": "重新加载账号配置失败",
        }


@mcp.tool()
def aliyun_get_account_info(account_key: str) -> dict:
    """
    获取指定账号的展示信息及 Markdown 详细说明（若已在 resources 中维护）。

    参数:
        account_key: 如 production、staging
    """
    try:
        if not validate_account(account_key):
            available = list_accounts()
            return {
                "error": f"账号 '{account_key}' 不存在",
                "available_accounts": available,
                "message": f"可用账号：{', '.join(available)}",
            }

        config = get_account_config(account_key)
        description_md = ACCOUNT_DESCRIPTIONS.get(account_key, "")
        description_summary = ACCOUNT_DESCRIPTIONS_SUMMARY.get(account_key, "暂无详细描述")

        return {
            "account_key": account_key,
            "account_name": config.account_name,
            "default_region": config.default_region,
            "uses_sts_role": bool(config.role_arn),
            "description": description_summary,
            "description_markdown": description_md,
            "message": f"已加载账号 {config.account_name} ({account_key}) 的背景信息，可继续调用只读 API。",
        }
    except Exception as e:
        return {
            "error": _safe_error_message(e, "账号信息加载异常（敏感细节已隐藏）"),
            "message": "获取账号信息失败",
        }


@mcp.tool()
def aliyun_list_supported_products() -> dict:
    """列出本 MCP 当前已接入与未接入的产品能力矩阵（用于能力边界判断）。"""
    integrated = []
    not_integrated = []
    for product_key, meta in PRODUCT_CAPABILITY_MATRIX.items():
        item = {
            "product": product_key,
            "aliases": meta.get("aliases", []),
            "enabled": bool(meta.get("enabled")),
            "tools": meta.get("tools", []),
        }
        if meta.get("note"):
            item["note"] = meta["note"]
        if item["enabled"]:
            integrated.append(item)
        else:
            not_integrated.append(item)

    return {
        "integrated_products": integrated,
        "not_integrated_products": not_integrated,
        "integrated_count": len(integrated),
        "not_integrated_count": len(not_integrated),
    }


@mcp.tool()
def aliyun_get_product_support_status(product: str) -> dict:
    """查询指定产品在当前 MCP 中是否已接入，并返回可用工具与替代路径。"""
    normalized_key = _normalize_product_key(product)
    if normalized_key in PRODUCT_CAPABILITY_MATRIX:
        meta = PRODUCT_CAPABILITY_MATRIX[normalized_key]
        if meta.get("enabled"):
            return {
                "product": normalized_key,
                "requested": product,
                "enabled": True,
                "tools": meta.get("tools", []),
                "message": f"产品 '{normalized_key}' 已接入，可直接使用对应工具查询。",
            }
        return {
            "product": normalized_key,
            "requested": product,
            "enabled": False,
            "tools": [],
            "note": meta.get("note", "当前 MCP 未接入该产品。"),
            "message": "当前版本暂不支持该产品的专用 API 查询。",
        }

    return {
        "product": normalized_key,
        "requested": product,
        "enabled": False,
        "tools": [],
        "message": "未在产品能力矩阵中识别该产品，请先调用 aliyun_list_supported_products 查看可用能力。",
    }


@mcp.tool()
def aliyun_healthcheck() -> dict:
    """检查 MCP 运行状态、账号配置可读性与推荐注册方式。"""
    health = {
        "mcp_service": "up",
        "tool_only_mode": True,
        "recommended_stdio_config": _recommended_stdio_config(),
    }

    try:
        account_keys = list_accounts()
        health["accounts_ready"] = True
        health["account_count"] = len(account_keys)
        health["account_keys"] = account_keys
    except Exception as e:
        health["accounts_ready"] = False
        health["account_count"] = 0
        health["account_keys"] = []
        health["account_error"] = _safe_error_message(e, "账号配置异常（敏感细节已隐藏）")
        health["recovery"] = "请修复 .env 后调用 aliyun_reload_account_configs，或重连 MCP 服务。"

    return health


@mcp.tool()
def aliyun_get_runtime_policy() -> dict:
    """返回本 MCP 的运行约束，确保对话在 MCP 工具内闭环。"""
    return {
        "tool_only_mode": True,
        "forbidden": [
            "terminal/shell/CLI 命令",
            "python -c / bash -c",
            "读取 ~/.hermes/* ~/.config/* ~/.aliyun/* 等宿主配置",
            "导出结果到本地后脚本二次解析",
        ],
        "required_flow": {
            "账号数量": "aliyun_get_account_count 或 aliyun_list_configured_accounts",
            "产品支持性": "aliyun_get_product_support_status",
            "服务可用性": "aliyun_healthcheck",
        },
        "on_unavailable": "仅提示用户重连 MCP 服务，不可改走本地命令。",
        "recommended_stdio_config": _recommended_stdio_config(),
    }


@mcp.tool()
def aliyun_bootstrap_session() -> dict:
    """会话入口摘要：返回账号状态、产品能力和运行策略，供模型首轮决策使用。"""
    health = aliyun_healthcheck()
    policy = aliyun_get_runtime_policy()
    products = aliyun_list_supported_products()

    account_count = health.get("account_count", 0)
    accounts_ready = bool(health.get("accounts_ready"))

    return {
        "session_ready": accounts_ready,
        "summary": {
            "tool_only_mode": True,
            "accounts_ready": accounts_ready,
            "account_count": account_count,
            "integrated_products": products.get("integrated_count", 0),
            "not_integrated_products": products.get("not_integrated_count", 0),
        },
        "healthcheck": health,
        "runtime_policy": policy,
        "product_matrix": products,
        "next_action": (
            "账号可用，按用户问题调用对应 aliyun_* 工具。"
            if accounts_ready
            else "账号未就绪，先修复 .env 并调用 aliyun_reload_account_configs。"
        ),
    }


@mcp.tool()
def aliyun_route_query_intent(question: str, account: str = "") -> dict:
    """根据自然语言问句自动路由到推荐工具，并尽量识别账号标识。"""
    q = _normalize_text(question)
    explicit_account = account.strip().lower() if account else ""
    resolved_account = explicit_account or _detect_account_from_text(q)

    scored: List[Dict[str, Any]] = []
    for rule in INTENT_RULES:
        score = 0
        hits: List[str] = []
        for kw in rule["keywords"]:
            if kw.lower() in q:
                score += 1
                hits.append(kw)
        if score > 0:
            scored.append(
                {
                    "intent": rule["intent"],
                    "score": score,
                    "keyword_hits": hits,
                    "recommended_tools": rule["tools"],
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        scored = [
            {
                "intent": "generic_query",
                "score": 0,
                "keyword_hits": [],
                "recommended_tools": ["aliyun_bootstrap_session", "aliyun_list_supported_products"],
            }
        ]

    primary = scored[0]
    next_tools: List[str] = list(primary["recommended_tools"])

    if primary["intent"] not in ["account_overview", "product_support_check"]:
        if not resolved_account:
            next_tools = ["aliyun_get_account_count"] + next_tools

    return {
        "question": question,
        "resolved_account": resolved_account,
        "primary_intent": primary["intent"],
        "candidate_intents": scored,
        "next_tools": next_tools,
        "needs_account": primary["intent"] not in ["account_overview", "product_support_check"],
        "message": "请按 next_tools 顺序继续调用；若 needs_account=true 且未识别账号，先让用户指定账号。",
    }


@mcp.tool()
def aliyun_get_account_resource_snapshot(account: str, region: str = "") -> dict:
    """按账号聚合查询核心资源数量，减少多工具串行调用导致的失败概率。"""
    if not validate_account(account):
        return {
            "success": False,
            "account": account,
            "error": f"无效账号标识: {account}",
        }

    rid = _get_region(account, region or None)
    out: Dict[str, Any] = {
        "success": True,
        "account": account,
        "region": rid,
        "summary": {},
        "errors": {},
    }

    try:
        ecs_client = get_ecs_client(account, rid)
        ecs_req = ecs_models.DescribeInstancesRequest(region_id=rid, page_size=1)
        ecs_resp = ecs_client.describe_instances_with_options(ecs_req, get_runtime_options())
        total = getattr(getattr(ecs_resp.body, "total_count", None), "real", None)
        out["summary"]["ecs_instances"] = int(total if total is not None else 0)
    except Exception as e:
        out["errors"]["ecs_instances"] = _safe_error_message(e, "ECS 查询失败")

    try:
        rds_client = get_rds_client(account, rid)
        rds_req = rds_models.DescribeDBInstancesRequest(region_id=rid, page_size=1)
        rds_resp = rds_client.describe_dbinstances_with_options(rds_req, get_runtime_options())
        items = getattr(getattr(rds_resp.body, "items", None), "dbinstance", None) or []
        total = getattr(getattr(rds_resp.body, "total_record_count", None), "real", None)
        out["summary"]["rds_instances"] = int(total if total is not None else len(items))
    except Exception as e:
        out["errors"]["rds_instances"] = _safe_error_message(e, "RDS 查询失败")

    try:
        redis_client = get_kvstore_client(account, rid)
        redis_req = kv_models.DescribeInstancesRequest(region_id=rid, page_size=1)
        redis_resp = redis_client.describe_instances_with_options(redis_req, get_runtime_options())
        total = getattr(getattr(redis_resp.body, "total_count", None), "real", None)
        out["summary"]["redis_instances"] = int(total if total is not None else 0)
    except Exception as e:
        out["errors"]["redis_instances"] = _safe_error_message(e, "Redis 查询失败")

    if out["errors"] and not out["summary"]:
        out["success"] = False

    out["message"] = "资源摘要查询完成"
    return out


register_all_prompts(mcp)
register_resources(mcp)


def main():
    parser = argparse.ArgumentParser(description="Alibaba Cloud multi-account MCP")
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "http"],
        help="stdio 或 http",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="HTTP 监听端口")

    args = parser.parse_args()

    try:
        account_count = len(list_accounts())
        print(f"阿里云 MCP 启动成功，已加载 {account_count} 个账号")
        print(f"传输方式：{args.transport}")
        if args.transport == "http":
            print(f"HTTP: http://{args.host}:{args.port}")
            print(f"SSE: http://{args.host}:{args.port}/sse")
    except Exception:
        print("账号配置预检查失败（敏感细节已隐藏），MCP 将继续启动。")
        print("请检查 ALIYUN_ACCOUNT_* 环境变量与 AccessKey 配置；可在修复后调用 aliyun_reload_account_configs。")
        print(f"传输方式：{args.transport}")
        if args.transport == "http":
            print(f"HTTP: http://{args.host}:{args.port}")
            print(f"SSE: http://{args.host}:{args.port}/sse")

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
