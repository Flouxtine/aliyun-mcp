"""
Alibaba Cloud multi-account MCP entrypoint.

Transports:
- stdio: local agents (Cursor, Claude Code, etc.)
- http: remote SSE clients
"""
import argparse
import base64
import csv
import io
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from aliyun_mcp.config.accounts import (
    get_account_config,
    get_all_accounts,
    get_config_diagnostics,
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
        "aliases": ["ecs", "云服务器", "云主机", "instance", "云盘", "快照", "备份策略"],
        "tools": [
            "aliyun_describe_instances",
            "aliyun_describe_disks",
            "aliyun_describe_snapshots",
            "aliyun_describe_auto_snapshot_policies",
            "aliyun_describe_auto_snapshot_policy_associations",
            "aliyun_find_public_security_group_rules",
        ],
    },
    "vpc": {
        "enabled": True,
        "aliases": ["vpc", "专有网络", "网络"],
        "tools": ["aliyun_describe_vpcs", "aliyun_describe_route_tables", "aliyun_describe_route_entries"],
    },
    "cloud_firewall": {
        "enabled": True,
        "aliases": ["云防火墙", "防火墙", "cloud firewall", "cloudfw", "公网防护", "互联网边界"],
        "tools": [
            "aliyun_describe_cloud_firewall_assets",
            "aliyun_get_cloud_firewall_public_ip_protection_status",
            "aliyun_describe_cloud_firewall_traffic_log",
            "aliyun_query_sls_logs",
        ],
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
        "tools": [
            "aliyun_list_alb_load_balancers",
            "aliyun_get_alb_load_balancer_attribute",
            "aliyun_list_alb_listeners",
            "aliyun_get_alb_listener_attribute",
        ],
    },
    "ssl_certificate": {
        "enabled": True,
        "aliases": ["ssl", "证书", "数字证书", "cas", "certificate", "https证书", "证书到期"],
        "tools": [
            "aliyun_list_ssl_certificates",
            "aliyun_list_ssl_certificate_orders",
            "aliyun_describe_ssl_certificate_state",
        ],
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
        "tools": ["aliyun_list_sls_projects", "aliyun_list_sls_logstores", "aliyun_query_sls_logs"],
    },
    "resource_center": {
        "enabled": True,
        "aliases": ["resourcecenter", "resource center", "资源中心", "全局资源", "资源检索", "全盘盘点"],
        "tools": ["aliyun_search_resource_center_resources", "aliyun_search_multi_account_resources"],
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
    "ram": {
        "enabled": True,
        "aliases": ["ram", "iam", "访问控制", "用户", "角色", "权限"],
        "tools": [
            "aliyun_list_ram_users",
            "aliyun_list_ram_roles",
            "aliyun_list_ram_policies",
            "aliyun_list_ram_access_keys",
        ],
    },
    "kms": {
        "enabled": True,
        "aliases": ["kms", "密钥管理", "key management"],
        "tools": ["aliyun_list_kms_keys", "aliyun_describe_kms_key"],
    },
    "waf": {
        "enabled": True,
        "aliases": ["waf", "web应用防火墙", "web firewall"],
        "tools": ["aliyun_describe_waf_instance", "aliyun_describe_waf_domains"],
    },
    "cdn": {
        "enabled": True,
        "aliases": ["cdn", "dcdn", "全站加速", "边缘加速"],
        "tools": ["aliyun_describe_cdn_domains", "aliyun_describe_dcdn_domains"],
    },
    "dns": {
        "enabled": True,
        "aliases": ["dns", "云解析", "alidns", "域名解析"],
        "tools": ["aliyun_describe_dns_domains", "aliyun_describe_dns_domain_records"],
    },
    "polardb": {
        "enabled": False,
        "aliases": ["polardb", "polar", "云原生数据库"],
        "tools": [],
        "note": "当前 MCP 尚未接入 PolarDB 集群、备份与性能查询。",
    },
    "nas": {
        "enabled": False,
        "aliases": ["nas", "文件存储", "filesystem"],
        "tools": [],
        "note": "当前 MCP 尚未接入 NAS 文件系统、挂载点与生命周期配置查询。",
    },
    "cen": {
        "enabled": True,
        "aliases": ["cen", "云企业网", "转发路由器", "tr"],
        "tools": ["aliyun_describe_cens", "aliyun_list_transit_routers"],
    },
    "cloud_config": {
        "enabled": True,
        "aliases": ["config", "cloud config", "配置审计", "合规规则"],
        "tools": [
            "aliyun_list_config_discovered_resources",
            "aliyun_list_config_rules",
            "aliyun_get_config_rule_compliance",
        ],
    },
    "security_center": {
        "enabled": True,
        "aliases": ["安全中心", "sas", "security center", "漏洞", "基线"],
        "tools": ["aliyun_describe_security_center_instances", "aliyun_describe_security_center_vul_list"],
    },
    "arms": {
        "enabled": False,
        "aliases": ["arms", "应用监控", "链路追踪", "apm"],
        "tools": [],
        "note": "当前 MCP 尚未接入 ARMS 应用监控、链路追踪与错误分析查询。",
    },
    "dts": {
        "enabled": False,
        "aliases": ["dts", "数据传输", "迁移", "同步任务"],
        "tools": [],
        "note": "当前 MCP 尚未接入 DTS 迁移、同步与订阅任务状态查询。",
    },
    "rocketmq": {
        "enabled": False,
        "aliases": ["rocketmq", "消息队列rocketmq", "消息队列", "mq"],
        "tools": [],
        "note": "当前 MCP 尚未接入 RocketMQ 实例、Topic、Group 与消费状态查询。",
    },
    "alikafka": {
        "enabled": False,
        "aliases": ["kafka", "alikafka", "消息队列kafka"],
        "tools": [],
        "note": "当前 MCP 尚未接入 ApsaraMQ for Kafka 实例、Topic、Group 与消费状态查询。",
    },
    "mse": {
        "enabled": False,
        "aliases": ["mse", "微服务引擎", "nacos", "网关"],
        "tools": [],
        "note": "当前 MCP 尚未接入 MSE 注册配置中心、云原生网关与治理规则查询。",
    },
    "fc": {
        "enabled": False,
        "aliases": ["fc", "函数计算", "function compute", "serverless"],
        "tools": [],
        "note": "当前 MCP 尚未接入函数计算服务、函数、触发器与版本别名查询。",
    },
    "sae": {
        "enabled": False,
        "aliases": ["sae", "serverless应用引擎"],
        "tools": [],
        "note": "当前 MCP 尚未接入 SAE 应用、实例、部署与弹性配置查询。",
    },
    "acr": {
        "enabled": False,
        "aliases": ["acr", "镜像仓库", "容器镜像服务", "registry"],
        "tools": [],
        "note": "当前 MCP 尚未接入 ACR 实例、命名空间、仓库、镜像版本与扫描结果查询。",
    },
    "asm": {
        "enabled": False,
        "aliases": ["asm", "服务网格", "service mesh"],
        "tools": [],
        "note": "当前 MCP 尚未接入 ASM 服务网格实例、数据面集群与网格配置查询。",
    },
    "maxcompute": {
        "enabled": True,
        "aliases": ["maxcompute", "odps", "大数据计算服务"],
        "tools": ["aliyun_list_maxcompute_quota_plans", "aliyun_list_maxcompute_instances"],
    },
    "dataworks": {
        "enabled": False,
        "aliases": ["dataworks", "数据开发", "数据集成"],
        "tools": [],
        "note": "当前 MCP 尚未接入 DataWorks 工作空间、任务、调度与数据集成作业查询。",
    },
    "hologres": {
        "enabled": False,
        "aliases": ["hologres", "holowarehouse"],
        "tools": [],
        "note": "当前 MCP 尚未接入 Hologres 实例、数据库、计算组与资源用量查询。",
    },
    "analyticdb": {
        "enabled": False,
        "aliases": ["analyticdb", "adb", "adb mysql", "adb postgresql", "分析型数据库"],
        "tools": [],
        "note": "当前 MCP 尚未接入 AnalyticDB MySQL/PostgreSQL 集群、资源组与性能查询。",
    },
    "emr": {
        "enabled": False,
        "aliases": ["emr", "开源大数据平台", "hadoop", "spark"],
        "tools": [],
        "note": "当前 MCP 尚未接入 EMR 集群、节点、作业与服务健康查询。",
    },
    "pai": {
        "enabled": False,
        "aliases": ["pai", "机器学习平台", "人工智能平台", "模型服务"],
        "tools": [],
        "note": "当前 MCP 尚未接入 PAI 工作空间、训练任务、模型与在线服务查询。",
    },
    "tablestore": {
        "enabled": True,
        "aliases": ["tablestore", "ots", "表格存储"],
        "tools": ["aliyun_list_tablestore_tables", "aliyun_describe_tablestore_instances"],
    },
    "lindorm": {
        "enabled": True,
        "aliases": ["lindorm", "hbase", "宽表"],
        "tools": ["aliyun_list_lindorm_instances", "aliyun_describe_lindorm_regions", "aliyun_get_lindorm_instance_summary"],
    },
    "anti_ddos": {
        "enabled": True,
        "aliases": ["ddos", "antiddos", "高防", "ddos防护", "ddos高防"],
        "tools": ["aliyun_describe_antiddos_instances", "aliyun_describe_antiddos_domains"],
    },
    "bastionhost": {
        "enabled": True,
        "aliases": ["bastionhost", "堡垒机", "运维安全中心"],
        "tools": [
            "aliyun_describe_bastionhost_instances",
            "aliyun_describe_bastionhost_hosts",
        ],
        "note": "当前 MCP 已支持堡垒机实例与资产查询，进一步支持可继续扩展。",
    },
    "vpn_gateway": {
        "enabled": True,
        "aliases": ["vpn", "vpn网关", "ipsec", "ssl-vpn"],
        "tools": ["aliyun_list_vpn_gateways", "aliyun_list_vpn_connections", "aliyun_list_ssl_vpn_servers"],
    },
    "express_connect": {
        "enabled": True,
        "aliases": ["expressconnect", "高速通道", "专线", "express connect", "物理专线"],
        "tools": ["aliyun_describe_express_connect_routers", "aliyun_describe_express_connect_router_regions", "aliyun_describe_express_connect_router_associations"],
    },
    "global_accelerator": {
        "enabled": True,
        "aliases": ["ga", "全球加速", "global accelerator"],
        "tools": ["aliyun_list_ga_accelerators", "aliyun_list_ga_listeners", "aliyun_list_ga_endpoint_groups"],
    },
    "privatelink": {
        "enabled": True,
        "aliases": ["privatelink", "私网连接", "终端节点", "endpoint"],
        "tools": ["aliyun_list_privatelink_endpoint_services", "aliyun_list_privatelink_endpoints"],
    },
    "eventbridge": {
        "enabled": True,
        "aliases": ["eventbridge", "事件总线"],
        "tools": ["aliyun_list_eventbridge_event_buses", "aliyun_list_eventbridge_connections", "aliyun_list_eventbridge_rules"],
    },
    "mns": {
        "enabled": True,
        "aliases": ["mns", "消息服务", "队列服务"],
        "tools": ["aliyun_list_mns_queues", "aliyun_list_mns_topics"],
    },
    "oos": {
        "enabled": True,
        "aliases": ["oos", "运维编排", "自动化运维"],
        "tools": ["aliyun_list_oos_templates", "aliyun_list_oos_executions", "aliyun_list_oos_parameters"],
    },
    "ros": {
        "enabled": True,
        "aliases": ["ros", "资源编排", "stack", "terraform"],
        "tools": ["aliyun_list_ros_stacks", "aliyun_describe_ros_resource_types", "aliyun_describe_ros_regions"],
    },
    "cloud_sso": {
        "enabled": True,
        "aliases": ["cloudsso", "cloud sso", "云sso", "单点登录"],
        "tools": ["aliyun_list_cloudsso_directories", "aliyun_list_cloudsso_users", "aliyun_list_cloudsso_groups"],
    },
    "elasticsearch": {
        "enabled": True,
        "aliases": ["es", "elasticsearch", "open search", "opensearch", "elk", "搜索引擎"],
        "tools": ["aliyun_describe_elasticsearch_instances"],
    },
    "rocketmq": {
        "enabled": True,
        "aliases": ["rocketmq", "mq", "消息队列", "message queue", "Apache RocketMQ"],
        "tools": ["aliyun_list_rocketmq_instances", "aliyun_list_rocketmq_topics", "aliyun_list_rocketmq_consumer_groups"],
    },
    "polardb": {
        "enabled": True,
        "aliases": ["polardb", "polar", "云原生数据库", "分布式数据库", "云数据库"],
        "tools": ["aliyun_describe_polardb_databases"],
    },
    "alikafka": {
        "enabled": True,
        "aliases": ["kafka", "alikafka", "消息队列kafka", "kafka消息队列"],
        "tools": ["aliyun_describe_alikafka_instances"],
    },
    "dts": {
        "enabled": True,
        "aliases": ["dts", "数据传输", "数据迁移", "数据同步"],
        "tools": ["aliyun_describe_dts_migration_jobs", "aliyun_describe_dts_subscription_instances"],
    },
    "nas": {
        "enabled": True,
        "aliases": ["nas", "文件存储", "filesystem"],
        "tools": ["aliyun_list_nas_filesystems"],
    },
    "mse": {
        "enabled": True,
        "aliases": ["mse", "微服务引擎", "nacos", "网关"],
        "tools": ["aliyun_list_mse_applications"],
    },
    "fc": {
        "enabled": True,
        "aliases": ["fc", "函数计算", "function compute", "serverless"],
        "tools": ["aliyun_list_fc_services", "aliyun_list_fc_functions"],
    },
    "sae": {
        "enabled": True,
        "aliases": ["sae", "serverless应用引擎"],
        "tools": ["aliyun_list_sae_applications"],
    },
    "dataworks": {
        "enabled": True,
        "aliases": ["dataworks", "数据开发", "数据集成"],
        "tools": ["aliyun_list_dataworks_projects"],
    },
    "hologres": {
        "enabled": True,
        "aliases": ["hologres", "holowarehouse"],
        "tools": ["aliyun_list_hologres_instances"],
    },
    "analyticdb": {
        "enabled": True,
        "aliases": ["analyticdb", "adb", "adb mysql", "adb postgresql", "分析型数据库"],
        "tools": ["aliyun_describe_analyticdb_instances"],
    },
    "emr": {
        "enabled": True,
        "aliases": ["emr", "开源大数据平台", "hadoop", "spark"],
        "tools": ["aliyun_list_emr_clusters"],
    },
    "pai": {
        "enabled": True,
        "aliases": ["pai", "机器学习平台", "人工智能平台", "模型服务"],
        "tools": ["aliyun_list_pai_dlc_jobs"],
    },
    "acr": {
        "enabled": True,
        "aliases": ["acr", "镜像仓库", "容器镜像服务", "registry"],
        "tools": ["aliyun_list_acr_namespaces"],
    },
    "asm": {
        "enabled": True,
        "aliases": ["asm", "服务网格", "service mesh"],
        "tools": ["aliyun_describe_asm_service_meshes"],
    },
    "arms": {
        "enabled": True,
        "aliases": ["arms", "应用监控", "链路追踪", "apm"],
        "tools": ["aliyun_list_arms_alerts"],
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
        "tools": ["aliyun_get_account_resource_snapshot", "aliyun_search_resource_center_resources", "aliyun_describe_instances"],
    },
    {
        "intent": "global_inventory",
        "keywords": ["全盘", "全量", "盘点", "资产清单", "全部资源", "跨账号资源", "resource center", "资源中心"],
        "tools": ["aliyun_search_resource_center_resources", "aliyun_search_multi_account_resources"],
    },
    {
        "intent": "ecs_backup_strategy",
        "keywords": ["备份", "快照", "自动快照", "快照策略", "备份策略", "snapshot", "auto snapshot", "backup"],
        "tools": [
            "aliyun_describe_auto_snapshot_policies",
            "aliyun_describe_auto_snapshot_policy_associations",
            "aliyun_describe_disks",
            "aliyun_describe_snapshots",
            "aliyun_lookup_events",
        ],
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
            "aliyun_describe_cens",
            "aliyun_list_transit_routers",
            "aliyun_list_vpn_gateways",
            "aliyun_list_vpn_connections",
            "aliyun_list_ssl_vpn_servers",
            "aliyun_list_privatelink_endpoint_services",
            "aliyun_list_privatelink_endpoints",
            "aliyun_list_ga_accelerators",
            "aliyun_describe_cdn_domains",
            "aliyun_describe_dcdn_domains",
        ],
    },
    {
        "intent": "security_group_public_exposure",
        "keywords": ["安全组", "0.0.0.0/0", "::/0", "全0", "公网开放", "开放端口", "security group"],
        "tools": ["aliyun_find_public_security_group_rules", "aliyun_describe_security_groups"],
    },
    {
        "intent": "cloud_firewall_public_ip_protection",
        "keywords": ["云防火墙", "防火墙", "公网防护", "互联网边界", "未受保护", "未保护", "已受保护", "公网ip", "cloudfw", "cloud firewall"],
        "tools": [
            "aliyun_get_cloud_firewall_public_ip_protection_status",
            "aliyun_describe_cloud_firewall_assets",
            "aliyun_describe_cloud_firewall_traffic_log",
            "aliyun_describe_eip_addresses",
            "aliyun_query_sls_logs",
        ],
    },
    {
        "intent": "sls_log_query",
        "keywords": ["访问日志", "流量日志", "源ip", "来源ip", "源访问ip", "谁访问", "3389", "rdp", "sls", "logstore", "日志查询"],
        "tools": ["aliyun_describe_cloud_firewall_traffic_log", "aliyun_list_sls_projects", "aliyun_list_sls_logstores", "aliyun_query_sls_logs"],
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
        "keywords": ["clb", "slb", "alb", "nlb", "负载均衡", "监听", "listener"],
        "tools": [
            "aliyun_describe_load_balancers",
            "aliyun_list_alb_load_balancers",
            "aliyun_list_alb_listeners",
            "aliyun_get_alb_listener_attribute",
            "aliyun_list_nlb_load_balancers",
        ],
    },
    {
        "intent": "certificate_expiration",
        "keywords": ["证书", "ssl", "https", "到期", "过期", "certificate", "cas"],
        "tools": [
            "aliyun_list_alb_listeners",
            "aliyun_get_alb_listener_attribute",
            "aliyun_list_ssl_certificates",
            "aliyun_list_ssl_certificate_orders",
            "aliyun_describe_ssl_certificate_state",
        ],
    },
    {
        "intent": "storage_logs_resources",
        "keywords": ["oss", "bucket", "对象存储", "sls", "logstore", "日志服务"],
        "tools": ["aliyun_list_oss_buckets", "aliyun_list_sls_projects", "aliyun_list_sls_logstores", "aliyun_query_sls_logs"],
    },
    {
        "intent": "product_support_check",
        "keywords": [
            "支持",
            "产品",
            "有没有",
            "ram",
            "kms",
            "waf",
            "cdn",
            "dcdn",
            "dns",
            "polardb",
            "nas",
            "cen",
            "配置审计",
            "安全中心",
            "arms",
            "dts",
            "es",
            "elasticsearch",
            "opensearch",
        ],
        "tools": ["aliyun_get_product_support_status", "aliyun_list_supported_products"],
    },
    {
        "intent": "report_formatting",
        "keywords": ["报告", "报表", "excel", "xlsx", "word", "docx", "ppt", "pptx", "pdf", "html", "csv", "导出", "生成文件", "表格"],
        "tools": [
            "aliyun_generate_report_docx",
            "aliyun_generate_report_pptx",
            "aliyun_generate_report_pdf",
            "aliyun_generate_report_html",
            "aliyun_generate_report_csv",
        ],
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


def _detect_unsupported_products_from_text(text: str) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    matched: List[str] = []
    for key, meta in PRODUCT_CAPABILITY_MATRIX.items():
        if meta.get("enabled"):
            continue
        candidates = [key] + list(meta.get("aliases", []))
        if any(str(candidate).lower() in normalized for candidate in candidates):
            matched.append(key)
    return matched

INSTRUCTIONS = """
你是阿里云运维助手，帮助用户在多账号环境下完成只读查询与排障。

## 执行方式（强制）

1. **仅使用 MCP 工具**：默认且必须通过本服务提供的 MCP tools 完成查询。
2. **禁止终端命令**：禁止建议或执行 terminal/shell/CLI 命令（包括 `date`、`aliyun ...`、`bash -c`、`python -c`、管道到解释器等）。
3. **禁止通用代码执行**：禁止使用 `execute_code`、notebook、浏览器自动化或任意宿主侧代码来解析、生成或保存结果。
4. **禁止外部脚本解析**：不要让用户把工具结果导出到本地文件再二次脚本处理。
5. **工具不足时处理**：若现有工具无法满足请求，直接说明受限点并给出可用工具内的替代方案。
6. **产品支持性问题**：用户询问“是否支持某产品（如 ES）”时，先调用 `aliyun_get_product_support_status`，不得凭空判断。
7. **禁止读取宿主本地配置文件**：不得通过 read_file/terminal/execute_code 等方式读取 `~/.hermes/*`、`~/.config/*`、`~/.aliyun/*` 等宿主文件来回答账号数量或能力问题。
8. **账号数量问题固定流程**：用户问“有几个阿里云账号/有哪些账号”时，必须先调用 `aliyun_get_account_count` 或 `aliyun_list_configured_accounts`。
9. **当前时间固定流程**：需要当前时间、日期、时区或报告生成时间时，必须调用 `aliyun_get_current_time`，不得执行 `date` 命令。
10. **连接异常处理**：如发现工具不可用或服务未连接，必须调用 `aliyun_healthcheck` 或提示“请重连 MCP 服务”，不得退回本地命令。
11. **会话首轮引导**：每个新会话第一条用户请求，优先调用 `aliyun_bootstrap_session` 获取账号、能力和策略摘要后再回答。
12. **自然语言自动路由**：用户给出自然语言问题时，先调用 `aliyun_route_query_intent` 生成推荐工具，再执行查询。
13. **报告生成约束**：用户要求 Word/DOCX/PPT/PPTX/PDF/HTML/Excel/CSV/报表/文件时，禁止使用 `python3 -c`、`execute_code`、`pip install`、`pandoc`、`openpyxl`、terminal、浏览器或外部脚本；Word/DOCX 必须调用 `aliyun_generate_report_docx`，PPT/PPTX 必须调用 `aliyun_generate_report_pptx`，PDF 必须调用 `aliyun_generate_report_pdf`，HTML 必须调用 `aliyun_generate_report_html`，CSV 必须调用 `aliyun_generate_report_csv`，或直接用 Markdown 表格回答。

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
- `aliyun_describe_disks` / `aliyun_describe_snapshots`：ECS 云盘与快照
- `aliyun_describe_auto_snapshot_policies` / `aliyun_describe_auto_snapshot_policy_associations`：ECS 自动快照策略与云盘绑定关系
- `aliyun_describe_rds_instances` / `aliyun_describe_rds_instance_attribute`：RDS 实例列表与详情
- `aliyun_describe_redis_instances` / `aliyun_describe_redis_instance_attribute`：Redis/Tair 实例列表与详情
- `aliyun_describe_mongodb_instances` / `aliyun_describe_mongodb_instance_attribute`：MongoDB 实例列表与详情
- `aliyun_find_public_security_group_rules`：聚合扫描安全组 0.0.0.0/0、::/0 等公网开放规则，优先用于安全组暴露面检查
- `aliyun_describe_security_groups` / `aliyun_describe_security_group_attribute`：安全组列表与规则详情
- `aliyun_describe_load_balancers` / `aliyun_describe_load_balancer_attribute`：CLB 列表与实例详情
- `aliyun_describe_load_balancer_listeners` / `aliyun_describe_slb_health_status`：CLB 监听配置与健康状态
- `aliyun_list_alb_load_balancers` / `aliyun_get_alb_load_balancer_attribute` / `aliyun_list_alb_listeners`：ALB 列表、详情与监听
- `aliyun_get_alb_listener_attribute`：ALB 监听详情与 HTTPS 证书 ID
- `aliyun_list_ssl_certificates`：SSL/CAS v2 证书列表与到期字段
- `aliyun_list_ssl_certificate_orders` / `aliyun_describe_ssl_certificate_state`：SSL/CAS v1 证书订单、状态信息
- `aliyun_list_nlb_load_balancers` / `aliyun_get_nlb_load_balancer_attribute` / `aliyun_list_nlb_listeners`：NLB 列表、详情与监听
- `aliyun_describe_eip_addresses` / `aliyun_describe_nat_gateways` / `aliyun_describe_route_tables` / `aliyun_describe_route_entries`：EIP、NAT 与路由查询
- `aliyun_describe_cloud_firewall_assets` / `aliyun_get_cloud_firewall_public_ip_protection_status` / `aliyun_describe_cloud_firewall_traffic_log`：云防火墙公网资产、防护状态与日志审计流量日志
- `aliyun_list_ram_users` / `aliyun_list_ram_roles` / `aliyun_list_ram_policies` / `aliyun_list_ram_access_keys`：RAM 用户、角色、策略与 AccessKey 元数据
- `aliyun_list_kms_keys` / `aliyun_describe_kms_key`：KMS 密钥列表与详情
- `aliyun_describe_dns_domains` / `aliyun_describe_dns_domain_records`：云解析 DNS 域名与记录查询
- `aliyun_describe_cdn_domains` / `aliyun_describe_dcdn_domains`：CDN/DCDN 加速域名查询
- `aliyun_describe_cens` / `aliyun_list_transit_routers`：CEN 与 TR 查询
- `aliyun_list_vpn_gateways` / `aliyun_list_vpn_connections` / `aliyun_list_ssl_vpn_servers`：VPN 网关、IPsec、SSL-VPN 查询
- `aliyun_list_privatelink_endpoint_services` / `aliyun_list_privatelink_endpoints`：PrivateLink 服务与终端节点查询
- `aliyun_list_ga_accelerators` / `aliyun_list_ga_listeners` / `aliyun_list_ga_endpoint_groups`：全球加速实例、监听、终端节点组查询
- `aliyun_describe_waf_instance` / `aliyun_describe_waf_domains`：WAF 实例与防护域名查询
- `aliyun_list_config_discovered_resources` / `aliyun_list_config_rules` / `aliyun_get_config_rule_compliance`：Cloud Config 资源发现与合规规则查询
- `aliyun_describe_security_center_instances` / `aliyun_describe_security_center_vul_list`：Security Center 资产与漏洞查询
- `aliyun_describe_antiddos_instances` / `aliyun_describe_antiddos_domains`：Anti-DDoS 实例与域名防护对象查询
- `aliyun_describe_ack_clusters`：ACK 集群列表
- `aliyun_list_oss_buckets` / `aliyun_get_oss_bucket_info`：OSS Bucket 列表与信息
- `aliyun_list_sls_projects` / `aliyun_list_sls_logstores` / `aliyun_query_sls_logs`：SLS Project、Logstore 与日志查询
- `aliyun_search_resource_center_resources`：资源中心单账号全局资源检索（跨产品）
- `aliyun_search_multi_account_resources`：资源中心跨账号全局资源检索（需多账号资源中心能力）
- `aliyun_list_tag_resources`：按标签或 ARN 查已标签资源（需 tags 或 resource_arns）
- `aliyun_list_support_resource_types`：标签服务支持的资源类型
- `aliyun_query_bill_overview`：账期账单总览
- `aliyun_describe_alert_history_list`：云监控告警历史
- `aliyun_lookup_events`：ActionTrail 事件检索
- `aliyun_list_supported_products`：查看本 MCP 已接入产品能力矩阵
- `aliyun_get_product_support_status`：查询指定产品是否已接入及可用工具
- `aliyun_healthcheck`：检查 MCP 运行状态与账号配置可读性
- `aliyun_get_runtime_policy`：返回本 MCP 的“仅工具模式”运行策略
- `aliyun_get_current_time`：返回当前时间，替代 terminal/date 命令
- `aliyun_bootstrap_session`：会话入口摘要（账号、能力矩阵、运行策略、健康状态）
- `aliyun_route_query_intent`：根据用户问句自动判断应调用的工具与账号
- `aliyun_get_account_resource_snapshot`：按账号一次性返回核心资源数量摘要（减少多次调用）
- `aliyun_get_config_diagnostics`：安全查看当前进程读取到的 `.env` 路径与账号标识
- `aliyun_generate_report_docx`：在 MCP 内生成 Word/DOCX 报告文件，避免本地脚本、pip、pandoc 和命令审批
- `aliyun_generate_report_pptx`：在 MCP 内生成 PPT/PPTX 报告文件
- `aliyun_generate_report_pdf`：在 MCP 内生成 PDF 报告文件
- `aliyun_generate_report_html`：在 MCP 内生成 HTML 报告文件
- `aliyun_generate_report_csv`：在 MCP 内生成 CSV 报表文本，避免本地脚本和命令审批
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


def _to_count(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    real_value = getattr(value, "real", None)
    if isinstance(real_value, (int, float)):
        return int(real_value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

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
            "diagnostics": get_config_diagnostics(),
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
def aliyun_get_current_time() -> dict:
    """返回 MCP 服务端当前时间，替代 terminal/date 命令。"""
    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)
    return {
        "success": True,
        "local_time": now_local.isoformat(timespec="seconds"),
        "utc_time": now_utc.isoformat(timespec="seconds"),
        "timezone": now_local.tzname(),
        "timestamp": int(now_local.timestamp()),
        "message": "当前时间已由 MCP 工具返回；不要再调用 terminal/date。",
    }


@mcp.tool()
def aliyun_healthcheck() -> dict:
    """检查 MCP 运行状态、账号配置可读性与推荐注册方式。"""
    health = {
        "mcp_service": "up",
        "tool_only_mode": True,
        "recommended_stdio_config": _recommended_stdio_config(),
        "config_diagnostics": get_config_diagnostics(),
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
            "date 命令（当前时间使用 aliyun_get_current_time）",
            "execute_code / notebook / 通用代码执行",
            "python -c / bash -c",
            "python3 -c / pip install / pandoc / openpyxl / 本地文档脚本生成",
            "browser 自动化生成文件",
            "read_file/write_file 读写宿主文件生成或解析报告",
            "读取 ~/.hermes/* ~/.config/* ~/.aliyun/* 等宿主配置",
            "导出结果到本地后脚本二次解析",
        ],
        "required_flow": {
            "账号数量": "aliyun_get_account_count 或 aliyun_list_configured_accounts",
            "当前时间": "aliyun_get_current_time",
            "产品支持性": "aliyun_get_product_support_status",
            "服务可用性": "aliyun_healthcheck",
            "报表生成": "Word/DOCX 使用 aliyun_generate_report_docx；PPT/PPTX 使用 aliyun_generate_report_pptx；PDF 使用 aliyun_generate_report_pdf；HTML 使用 aliyun_generate_report_html；CSV 使用 aliyun_generate_report_csv；也可用 Markdown 表格",
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
def aliyun_get_config_diagnostics() -> dict:
    """安全诊断当前 MCP 进程实际读取到的配置来源与账号标识，不返回任何密钥。"""
    return get_config_diagnostics()


REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _safe_report_filename(title: str, filename: str = "", extension: str = "docx") -> str:
    extension = extension.lstrip(".").lower()
    base = filename or title or "aliyun-report"
    base = Path(base).name
    base = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", base).strip("._-")
    if not base:
        base = "aliyun-report"
    suffix = f".{extension}"
    if not base.lower().endswith(suffix):
        base = f"{base}{suffix}"
    stem = base[: -len(suffix)]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}{suffix}"


def _parse_report_payload(content_markdown: str, headers_json: str, rows_json: str) -> tuple[List[str], List[Any], Optional[str]]:
    try:
        headers = json.loads(headers_json or "[]")
        rows = json.loads(rows_json or "[]")
    except json.JSONDecodeError as e:
        return [], [], f"headers_json 或 rows_json 不是合法 JSON: {e.msg}"

    if not isinstance(headers, list) or not all(isinstance(item, str) for item in headers):
        return [], [], "headers_json 必须是字符串数组"
    if not isinstance(rows, list):
        return [], [], "rows_json 必须是数组"
    if not content_markdown and not rows:
        return [], [], "content_markdown 或 rows_json 至少提供一个"
    return headers, rows, None


def _normalize_table_rows(headers: List[str], rows: List[Any]) -> List[List[Any]]:
    normalized_rows = _normalize_table_rows(headers, rows)
    return normalized_rows


def _markdown_to_plain_lines(markdown: str) -> List[str]:
    lines: List[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        elif line.startswith(("- ", "* ")):
            line = "• " + line[2:].strip()
        lines.append(line)
    return lines


def _docx_paragraph(text: str, style: str = "") -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    lines = str(text).split("\n")
    runs: List[str] = []
    for index, line in enumerate(lines):
        if index > 0:
            runs.append("<w:r><w:br/></w:r>")
        runs.append(f"<w:r><w:t>{escape(line)}</w:t></w:r>")
    return f"<w:p>{style_xml}{''.join(runs)}</w:p>"


def _docx_table(headers: List[str], rows: List[Any]) -> str:
    def cell(value: Any) -> str:
        return f"<w:tc><w:p><w:r><w:t>{escape(str(value))}</w:t></w:r></w:p></w:tc>"

    def row(values: List[Any]) -> str:
        return "<w:tr>" + "".join(cell(value) for value in values) + "</w:tr>"

    normalized_rows: List[List[Any]] = []
    for item in rows:
        if isinstance(item, dict):
            normalized_rows.append([item.get(header, "") for header in headers])
        elif isinstance(item, list):
            normalized_rows.append(item)
        else:
            normalized_rows.append([item])

    borders = "".join(
        f'<w:{name} w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        for name in ["top", "left", "bottom", "right", "insideH", "insideV"]
    )
    table = [f"<w:tbl><w:tblPr><w:tblBorders>{borders}</w:tblBorders></w:tblPr>"]
    if headers:
        table.append(row(headers))
    table.extend(row(item) for item in normalized_rows)
    table.append("</w:tbl>")
    return "".join(table)


def _markdown_lines_to_docx(markdown: str) -> List[str]:
    blocks: List[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip()
        line = raw.strip()
        if not line:
            index += 1
            continue

        if line.startswith("|") and "|" in line[1:]:
            table_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate.startswith("|"):
                    break
                table_lines.append(candidate)
                index += 1
            rows = [[cell.strip() for cell in item.strip("|").split("|")] for item in table_lines]
            if len(rows) >= 2 and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in rows[1]):
                blocks.append(_docx_table(rows[0], rows[2:]))
            else:
                blocks.append(_docx_table(rows[0], rows[1:]))
            continue

        if line.startswith("### "):
            blocks.append(_docx_paragraph(line[4:], "Heading3"))
        elif line.startswith("## "):
            blocks.append(_docx_paragraph(line[3:], "Heading2"))
        elif line.startswith("# "):
            blocks.append(_docx_paragraph(line[2:], "Heading1"))
        elif line.startswith(("- ", "* ")):
            blocks.append(_docx_paragraph("\u2022 " + line[2:]))
        elif re.match(r"^\d+[.)]\s+", line):
            blocks.append(_docx_paragraph(line))
        else:
            blocks.append(_docx_paragraph(raw))
        index += 1
    return blocks


def _write_docx(path: Path, title: str, content_markdown: str, headers: List[str], rows: List[Any]) -> None:
    body_blocks: List[str] = []
    if title:
        body_blocks.append(_docx_paragraph(title, "Title"))
    body_blocks.extend(_markdown_lines_to_docx(content_markdown or ""))
    if headers or rows:
        if content_markdown:
            body_blocks.append(_docx_paragraph("附表", "Heading2"))
        body_blocks.append(_docx_table(headers, rows))

    section = (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" '
        'w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(body_blocks)}{section}</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    document_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>'
        '</w:styles>'
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/_rels/document.xml.rels", document_rels)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)


def _html_from_report(title: str, content_markdown: str, headers: List[str], rows: List[Any]) -> str:
    body: List[str] = []
    if title:
        body.append(f"<h1>{escape(title)}</h1>")
    for line in content_markdown.splitlines():
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            body.append(f"<h3>{escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            body.append(f"<h2>{escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            body.append(f"<h1>{escape(stripped[2:])}</h1>")
        elif stripped.startswith(("- ", "* ")):
            body.append(f"<p>• {escape(stripped[2:])}</p>")
        else:
            body.append(f"<p>{escape(raw)}</p>")
    if headers or rows:
        body.append("<table><thead><tr>")
        for header in headers:
            body.append(f"<th>{escape(header)}</th>")
        body.append("</tr></thead><tbody>")
        for row in _normalize_table_rows(headers, rows):
            body.append("<tr>")
            for value in row:
                body.append(f"<td>{escape(str(value))}</td>")
            body.append("</tr>")
        body.append("</tbody></table>")
    return """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; color: #1f2937; line-height: 1.6; }}
    h1 {{ font-size: 26px; margin: 0 0 18px; }}
    h2 {{ font-size: 20px; margin: 24px 0 10px; }}
    h3 {{ font-size: 16px; margin: 18px 0 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; font-size: 13px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #f3f4f6; text-align: left; }}
  </style>
</head>
<body>
{body}
</body>
</html>
""".format(title=escape(title or "阿里云报告"), body="\n".join(body))


def _write_html(path: Path, title: str, content_markdown: str, headers: List[str], rows: List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html_from_report(title, content_markdown, headers, rows), encoding="utf-8")


def _pdf_hex_text(text: str) -> str:
    return ("feff" + str(text).encode("utf-16-be").hex()).upper()


def _write_pdf(path: Path, title: str, content_markdown: str, headers: List[str], rows: List[Any]) -> None:
    lines: List[str] = []
    if title:
        lines.append(title)
    lines.extend(_markdown_to_plain_lines(content_markdown))
    if headers or rows:
        if headers:
            lines.append(" | ".join(headers))
        for row in _normalize_table_rows(headers, rows):
            lines.append(" | ".join(str(value) for value in row))

    pages = [lines[index : index + 38] for index in range(0, len(lines), 38)] or [[title or "阿里云报告"]]
    objects: List[bytes] = []

    def add_object(content: str | bytes) -> int:
        data = content.encode("utf-8") if isinstance(content, str) else content
        objects.append(data)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    font_id = add_object("<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>")
    add_object("<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> >>")
    page_ids: List[int] = []
    for page_lines in pages:
        commands = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for line_index, line in enumerate(page_lines):
            if line_index > 0:
                commands.append("T*")
            commands.append(f"<{_pdf_hex_text(line[:110])}> Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("utf-8")
        content_id = add_object(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = add_object(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>".encode("utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    path.write_bytes(bytes(output))


def _pptx_text_body(lines: List[str]) -> str:
    paragraphs = []
    for line in lines:
        paragraphs.append(
            '<a:p><a:r><a:rPr lang="zh-CN" sz="1800"/><a:t>' + escape(line) + '</a:t></a:r></a:p>'
        )
    return "".join(paragraphs)


def _write_pptx(path: Path, title: str, content_markdown: str, headers: List[str], rows: List[Any]) -> None:
    lines = _markdown_to_plain_lines(content_markdown)
    if headers or rows:
        if headers:
            lines.append(" | ".join(headers))
        for row in _normalize_table_rows(headers, rows):
            lines.append(" | ".join(str(value) for value in row))
    chunks = [lines[index : index + 9] for index in range(0, len(lines), 9)] or [[]]

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
    ]
    for index in range(1, len(chunks) + 1):
        content_types.append(f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    content_types.append('</Types>')

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '</Relationships>'
    )
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{index}"/>' for index in range(1, len(chunks) + 1))
    presentation_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="9144000" cy="5143500" type="screen16x9"/></p:presentation>'
    )
    presentation_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for index in range(1, len(chunks) + 1):
        presentation_rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>')
    presentation_rels.append('</Relationships>')

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as pptx:
        pptx.writestr("[Content_Types].xml", "".join(content_types))
        pptx.writestr("_rels/.rels", root_rels)
        pptx.writestr("ppt/presentation.xml", presentation_xml)
        pptx.writestr("ppt/_rels/presentation.xml.rels", "".join(presentation_rels))
        for index, chunk in enumerate(chunks, start=1):
            slide_title = title if index == 1 else f"{title} ({index})"
            slide_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
                '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="457200" y="274320"/><a:ext cx="8229600" cy="685800"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="3200" b="1"/><a:t>'
                + escape(slide_title or "阿里云报告")
                + '</a:t></a:r></a:p></p:txBody></p:sp>'
                '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="609600" y="1143000"/><a:ext cx="7924800" cy="3657600"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/>'
                + _pptx_text_body(chunk)
                + '</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
            )
            pptx.writestr(f"ppt/slides/slide{index}.xml", slide_xml)
            pptx.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')


def _report_file_payload(path: Path, report_format: str, title: str, row_count: int, include_base64: bool) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": True,
        "format": report_format,
        "title": title,
        "row_count": row_count,
        "file_path": str(path),
        "relative_path": str(path.relative_to(Path(__file__).resolve().parent)),
        "message": f"已在 MCP 内生成 {report_format.upper()} 文件。不要再调用 terminal、python、pip、pandoc 或 write_file 生成文档。",
    }
    if include_base64:
        payload["base64_content"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return payload


@mcp.tool()
def aliyun_generate_report_docx(
    title: str,
    content_markdown: str = "",
    headers_json: str = "[]",
    rows_json: str = "[]",
    filename: str = "",
    include_base64: bool = False,
) -> dict:
    """在 MCP 内生成 Word/DOCX 报告文件，避免通过 terminal/python/pip/pandoc/write_file 触发审批。"""
    headers, rows, error = _parse_report_payload(content_markdown, headers_json, rows_json)
    if error:
        return {"success": False, "error": error}

    out_path = REPORTS_DIR / _safe_report_filename(title, filename, "docx")
    _write_docx(out_path, title, content_markdown, headers, rows)
    return _report_file_payload(out_path, "docx", title, len(rows), include_base64)


@mcp.tool()
def aliyun_generate_report_html(
    title: str,
    content_markdown: str = "",
    headers_json: str = "[]",
    rows_json: str = "[]",
    filename: str = "",
    include_base64: bool = False,
) -> dict:
    """在 MCP 内生成 HTML 报告文件，避免通过 terminal/python/write_file 触发审批。"""
    headers, rows, error = _parse_report_payload(content_markdown, headers_json, rows_json)
    if error:
        return {"success": False, "error": error}
    out_path = REPORTS_DIR / _safe_report_filename(title, filename, "html")
    _write_html(out_path, title, content_markdown, headers, rows)
    return _report_file_payload(out_path, "html", title, len(rows), include_base64)


@mcp.tool()
def aliyun_generate_report_pdf(
    title: str,
    content_markdown: str = "",
    headers_json: str = "[]",
    rows_json: str = "[]",
    filename: str = "",
    include_base64: bool = False,
) -> dict:
    """在 MCP 内生成 PDF 报告文件，避免通过 terminal/python/pandoc/write_file 触发审批。"""
    headers, rows, error = _parse_report_payload(content_markdown, headers_json, rows_json)
    if error:
        return {"success": False, "error": error}
    out_path = REPORTS_DIR / _safe_report_filename(title, filename, "pdf")
    _write_pdf(out_path, title, content_markdown, headers, rows)
    return _report_file_payload(out_path, "pdf", title, len(rows), include_base64)


@mcp.tool()
def aliyun_generate_report_pptx(
    title: str,
    content_markdown: str = "",
    headers_json: str = "[]",
    rows_json: str = "[]",
    filename: str = "",
    include_base64: bool = False,
) -> dict:
    """在 MCP 内生成 PPT/PPTX 报告文件，避免通过 terminal/python/pandoc/write_file 触发审批。"""
    headers, rows, error = _parse_report_payload(content_markdown, headers_json, rows_json)
    if error:
        return {"success": False, "error": error}
    out_path = REPORTS_DIR / _safe_report_filename(title, filename, "pptx")
    _write_pptx(out_path, title, content_markdown, headers, rows)
    return _report_file_payload(out_path, "pptx", title, len(rows), include_base64)


@mcp.tool()
def aliyun_generate_report_csv(title: str, headers_json: str, rows_json: str) -> dict:
    """在 MCP 内生成 CSV 报表文本，避免通过 terminal/python -c/openpyxl 触发审批。"""
    try:
        headers = json.loads(headers_json)
        rows = json.loads(rows_json)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"headers_json 或 rows_json 不是合法 JSON: {e.msg}",
        }

    if not isinstance(headers, list) or not all(isinstance(item, str) for item in headers):
        return {"success": False, "error": "headers_json 必须是字符串数组"}
    if not isinstance(rows, list):
        return {"success": False, "error": "rows_json 必须是数组"}

    output = io.StringIO()
    writer = csv.writer(output)
    if title:
        writer.writerow([title])
    writer.writerow(headers)

    for row in rows:
        if isinstance(row, dict):
            writer.writerow([row.get(header, "") for header in headers])
        elif isinstance(row, list):
            writer.writerow(row)
        else:
            writer.writerow([row])

    return {
        "success": True,
        "format": "csv",
        "title": title,
        "row_count": len(rows),
        "csv_content": output.getvalue(),
        "message": "已生成 CSV 文本。为避免审批弹窗，本 MCP 不使用 terminal/python/openpyxl 生成本地文件。",
    }


@mcp.tool()
def aliyun_route_query_intent(question: str, account: str = "") -> dict:
    """根据自然语言问句自动路由到推荐工具，并尽量识别账号标识。"""
    q = _normalize_text(question)
    explicit_account = account.strip().lower() if account else ""
    resolved_account = explicit_account or _detect_account_from_text(q)
    unsupported_products = _detect_unsupported_products_from_text(q)

    scored: List[Dict[str, Any]] = []
    if unsupported_products:
        scored.append(
            {
                "intent": "product_support_check",
                "score": 100,
                "keyword_hits": unsupported_products,
                "recommended_tools": ["aliyun_get_product_support_status", "aliyun_list_supported_products"],
            }
        )
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
        out["summary"]["ecs_instances"] = _to_count(getattr(ecs_resp.body, "total_count", None))
    except Exception as e:
        out["errors"]["ecs_instances"] = _safe_error_message(e, "ECS 查询失败")

    try:
        rds_client = get_rds_client(account, rid)
        rds_req = rds_models.DescribeDBInstancesRequest(region_id=rid, page_size=1)
        rds_resp = rds_client.describe_dbinstances_with_options(rds_req, get_runtime_options())
        items = getattr(getattr(rds_resp.body, "items", None), "dbinstance", None) or []
        out["summary"]["rds_instances"] = _to_count(getattr(rds_resp.body, "total_record_count", None), len(items))
    except Exception as e:
        out["errors"]["rds_instances"] = _safe_error_message(e, "RDS 查询失败")

    try:
        redis_client = get_kvstore_client(account, rid)
        redis_req = kv_models.DescribeInstancesRequest(region_id=rid, page_size=1)
        redis_resp = redis_client.describe_instances_with_options(redis_req, get_runtime_options())
        out["summary"]["redis_instances"] = _to_count(getattr(redis_resp.body, "total_count", None))
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
