"""
Read-only tools for common Alibaba Cloud products.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import oss2
from aliyun.log import LogClient
from alibabacloud_alb20200616 import models as alb_models
from alibabacloud_alidns20150109 import models as alidns_models
from alibabacloud_cbn20170912 import models as cbn_models
from alibabacloud_cdn20180510 import models as cdn_models
from alibabacloud_config20200907 import models as config_models
from alibabacloud_cs20151215 import models as cs_models
from alibabacloud_dcdn20180115 import models as dcdn_models
from alibabacloud_ddoscoo20200101 import models as ddoscoo_models
from alibabacloud_dds20151201 import models as dds_models
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_ga20191120 import models as ga_models
from alibabacloud_kms20160120 import models as kms_models
from alibabacloud_sas20181203 import models as sas_models
from alibabacloud_waf_openapi20211001 import models as waf_models
from alibabacloud_polardb20170801 import models as polardb_models
from alibabacloud_elasticsearch20170613 import models as es_models
from alibabacloud_rocketmq20220801 import models as rmq_models
from alibabacloud_alikafka20190916 import models as kafka_models
from alibabacloud_dts20200101 import models as dts_models
from alibabacloud_mse20190531 import models as mse_models
from alibabacloud_fc_open20210406 import models as fc_models
from alibabacloud_sae20190506 import models as sae_models
from alibabacloud_dataworks_public20200518 import models as dataworks_models
from alibabacloud_gpdb20160503 import models as gpdb_models
from alibabacloud_emr20160408 import models as emr_models
from alibabacloud_pai_dlc20201203 import models as pai_models
from alibabacloud_nas20170626 import models as nas_models
from alibabacloud_hologram20220601 import models as hologram_models
from alibabacloud_cr20181201 import models as acr_models
from alibabacloud_servicemesh20200111 import models as asm_models
from alibabacloud_arms20190808 import models as arms_models
from alibabacloud_maxcompute20220104 import models as maxcompute_models
from alibabacloud_eventbridge20200401 import models as eventbridge_models
from alibabacloud_mns_open20220119 import models as mns_models
from alibabacloud_ros20190910 import models as ros_models
from alibabacloud_nlb20220430 import models as nlb_models
from alibabacloud_ram20150501 import models as ram_models
from alibabacloud_rds20140815 import models as rds_models
from alibabacloud_r_kvstore20150101 import models as kv_models
from alibabacloud_slb20140515 import models as slb_models
from alibabacloud_tag20180828 import models as tag_models
from alibabacloud_tea_openapi import utils_models as open_api_util_models
from alibabacloud_vpc20160428 import models as vpc_models

from aliyun_mcp.config.accounts import validate_account
from aliyun_mcp.core.client_factory import (
    get_alidns_client,
    get_alb_client,
    get_cbn_client,
    get_cdn_client,
    get_config_client,
    get_cs_client,
    get_dcdn_client,
    get_ddoscoo_client,
    get_dds_client,
    get_ecs_client,
    get_ga_client,
    get_kms_client,
    get_kvstore_client,
    get_nlb_client,
    get_ram_client,
    get_rds_client,
    get_resolved_credentials,
    get_runtime_options,
    get_sas_client,
    get_slb_client,
    get_tag_client,
    get_vpc_client,
    get_waf_client,
    get_polardb_client,
    get_elasticsearch_client,
    get_rocketmq_client,
    get_alikafka_client,
    get_dts_client,
    get_mse_client,
    get_fc_client,
    get_sae_client,
    get_dataworks_client,
    get_gpdb_client,
    get_emr_client,
    get_pai_dlc_client,
    get_nas_client,
    get_hologram_client,
    get_cr_client,
    get_servicemesh_client,
    get_arms_client,
    get_maxcompute_client,
    get_eventbridge_client,
    get_mns_client,
    get_ros_client,
)
from aliyun_mcp.utils.serialize import openapi_response_to_dict


def _get_cas_client(account: str, region: Optional[str]):
    try:
        from alibabacloud_cas20200407.client import Client as CasClient
    except ImportError as e:
        raise ValueError("SSL 证书查询需要依赖 alibabacloud_cas20200407，请先安装 requirements.txt。") from e

    rid = _get_region(account, region)
    creds = get_resolved_credentials(account)
    cfg = open_api_util_models.Config(
        access_key_id=creds.access_key_id,
        access_key_secret=creds.access_key_secret,
        security_token=creds.security_token,
        region_id=rid,
        read_timeout=120000,
        connect_timeout=10000,
    )
    return rid, CasClient(cfg)


def _get_cloudfw_client(account: str, region: Optional[str]):
    try:
        from alibabacloud_cloudfw20171207.client import Client as CloudfwClient
    except ImportError as e:
        raise ValueError("云防火墙查询需要依赖 alibabacloud_cloudfw20171207，请先安装 requirements.txt。") from e

    rid = _get_region(account, region)
    creds = get_resolved_credentials(account)
    cfg = open_api_util_models.Config(
        access_key_id=creds.access_key_id,
        access_key_secret=creds.access_key_secret,
        security_token=creds.security_token,
        region_id=rid,
        endpoint="cloudfw.aliyuncs.com",
        read_timeout=120000,
        connect_timeout=10000,
    )
    return rid, CloudfwClient(cfg)


def _get_resourcecenter_client(account: str, region: Optional[str]):
    try:
        from alibabacloud_resourcecenter20221201.client import Client as ResourceCenterClient
        from alibabacloud_resourcecenter20221201 import models as resourcecenter_models
    except ImportError as e:
        raise ValueError("资源中心查询需要依赖 alibabacloud_resourcecenter20221201，请先安装 requirements.txt。") from e

    rid = _get_region(account, region)
    creds = get_resolved_credentials(account)
    cfg = open_api_util_models.Config(
        access_key_id=creds.access_key_id,
        access_key_secret=creds.access_key_secret,
        security_token=creds.security_token,
        region_id=rid,
        read_timeout=120000,
        connect_timeout=10000,
    )
    return rid, ResourceCenterClient(cfg), resourcecenter_models


def _set_if_present(obj, name: str, value) -> None:
    if value is not None and hasattr(obj, name):
        setattr(obj, name, value)


_PUBLIC_IP_KEYS = ["InternetAddress", "PublicIp", "PublicIpAddress", "EipAddress", "InternetIp", "Ip", "IP", "Address"]
_PROTECTION_KEYS = [
    "ProtectStatus",
    "ProtectionStatus",
    "Protected",
    "IsProtected",
    "CfwStatus",
    "FirewallStatus",
    "Status",
]


def _first_present(item: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in item and item[key] not in [None, ""]:
            return item[key]
    lowered = {str(k).lower(): v for k, v in item.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in [None, ""]:
            return value
    return None


def _collect_cloudfw_asset_items(value: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        if _first_present(value, _PUBLIC_IP_KEYS) is not None or _first_present(value, _PROTECTION_KEYS) is not None:
            items.append(value)
        for child in value.values():
            items.extend(_collect_cloudfw_asset_items(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(_collect_cloudfw_asset_items(child))
    return items


def _classify_cloudfw_protection(value: Any) -> str:
    text = str(value).strip().lower() if value is not None else ""
    protected_values = {"1", "true", "yes", "y", "on", "open", "opened", "enabled", "enable", "protected", "normal", "protecting", "已防护", "已开启"}
    unprotected_values = {"0", "false", "no", "n", "off", "close", "closed", "disabled", "disable", "unprotected", "notprotected", "未保护", "未防护", "未开启"}
    if text in protected_values:
        return "protected"
    if text in unprotected_values:
        return "unprotected"
    return "unknown"


def _get_region(account: str, region: Optional[str]) -> str:
    from aliyun_mcp.config.accounts import get_account_config

    return region or get_account_config(account).default_region


def _get_oss_service(account: str, region: Optional[str]):
    rid = _get_region(account, region)
    creds = get_resolved_credentials(account)
    endpoint = f"https://oss-{rid}.aliyuncs.com"
    if creds.security_token:
        auth = oss2.StsAuth(creds.access_key_id, creds.access_key_secret, creds.security_token)
    else:
        auth = oss2.Auth(creds.access_key_id, creds.access_key_secret)
    return rid, auth, oss2.Service(auth, endpoint)


def _get_sls_client(account: str, region: Optional[str]) -> tuple[str, LogClient]:
    rid = _get_region(account, region)
    creds = get_resolved_credentials(account)
    endpoint = f"{rid}.log.aliyuncs.com"
    client = LogClient(
        endpoint,
        creds.access_key_id,
        creds.access_key_secret,
        securityToken=creds.security_token,
    )
    return rid, client


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_sls_time(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("SLS 时间参数不能是布尔值")
    if isinstance(value, (int, float)):
        seconds = int(value)
        return seconds // 1000 if seconds > 10_000_000_000 else seconds
    text = str(value).strip()
    if not text:
        raise ValueError("SLS 时间参数不能为空")
    if text.isdigit():
        seconds = int(text)
        return seconds // 1000 if seconds > 10_000_000_000 else seconds
    iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso_text)
    except ValueError as e:
        raise ValueError("SLS 时间参数需为 Unix 秒/毫秒时间戳或 ISO8601，例如 2026-05-22T00:00:00Z") from e
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def _sls_log_to_dict(log: Any) -> Dict[str, Any]:
    if hasattr(log, "_to_dict"):
        return log._to_dict()
    if isinstance(log, dict):
        return log
    out: Dict[str, Any] = {}
    if hasattr(log, "get_time"):
        out["__time__"] = str(log.get_time())
    if hasattr(log, "get_source"):
        out["__source__"] = log.get_source()
    if hasattr(log, "get_contents"):
        contents = log.get_contents()
        if isinstance(contents, dict):
            out.update(contents)
        else:
            out["contents"] = contents
    return out or {"value": str(log)}


def _cloudfw_body_items(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = result.get("body") if isinstance(result, dict) else None
    if not isinstance(body, dict):
        return []
    items = body.get("DataList") or body.get("dataList") or []
    return [item for item in _as_list(items) if isinstance(item, dict)]


def _get_path(value: Dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _security_group_items(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in _as_list(_get_path(body, "SecurityGroups", "SecurityGroup")) if isinstance(item, dict)]


def _permission_items(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in _as_list(_get_path(body, "Permissions", "Permission")) if isinstance(item, dict)]


def _rule_cidrs(rule: Dict[str, Any]) -> List[str]:
    fields = ["SourceCidrIp", "Ipv6SourceCidrIp", "DestCidrIp", "Ipv6DestCidrIp"]
    return [str(rule[field]).strip() for field in fields if rule.get(field) not in [None, ""]]


def register(mcp):
    @mcp.tool()
    def aliyun_list_support_resource_types(
        account: str,
        region: Optional[str] = None,
        product_code: Optional[str] = None,
        next_token: Optional[str] = None,
        max_result: int = 50,
    ) -> Dict[str, Any]:
        """
        查询标签服务支持的资源类型（用于构造 ResourceARN 或理解可打标签资源）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认使用账号默认区域
            product_code: 可选，产品代码过滤（如 ecs）
            next_token: 分页令牌
            max_result: 每页条数，最大 1000
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_tag_client(account, rid)
        req = tag_models.ListSupportResourceTypesRequest(
            region_id=rid,
            product_code=product_code,
            next_token=next_token,
            max_result=max_result,
        )
        resp = client.list_support_resource_types_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_oss_buckets(
        account: str,
        region: Optional[str] = None,
        prefix: Optional[str] = None,
        max_keys: int = 100,
    ) -> Dict[str, Any]:
        """
        列出 OSS Bucket（基于 oss2 Service API，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            prefix: Bucket 名称前缀过滤
            max_keys: 返回条数上限
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid, _auth, service = _get_oss_service(account, region)
        buckets = []
        for bucket in oss2.BucketIterator(service, prefix=prefix, max_keys=max_keys):
            buckets.append(
                {
                    "name": bucket.name,
                    "location": getattr(bucket, "location", None),
                    "creation_date": getattr(bucket, "creation_date", None),
                    "extranet_endpoint": getattr(bucket, "extranet_endpoint", None),
                    "intranet_endpoint": getattr(bucket, "intranet_endpoint", None),
                }
            )
        return {"region": rid, "count": len(buckets), "buckets": buckets}

    @mcp.tool()
    def aliyun_get_oss_bucket_info(
        account: str,
        bucket_name: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 OSS Bucket 基本信息（基于 oss2 Bucket API，只读）。

        参数:
            account: 账号标识（必填）
            bucket_name: Bucket 名称（必填）
            region: 区域，默认账号默认区域
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid, auth, _service = _get_oss_service(account, region)
        endpoint = f"https://oss-{rid}.aliyuncs.com"
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        info = bucket.get_bucket_info()
        return {
            "region": rid,
            "bucket_name": bucket_name,
            "info": getattr(info, "bucket", None).__dict__ if getattr(info, "bucket", None) is not None else str(info),
        }

    @mcp.tool()
    def aliyun_list_tag_resources(
        account: str,
        region: Optional[str] = None,
        tags: Optional[str] = None,
        resource_arns: Optional[List[str]] = None,
        category: Optional[str] = None,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询已打标签的资源（ListTagResources）。OpenAPI 要求 **Tags 与 ResourceARN 至少填一类**。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            tags: 标签过滤 JSON 数组字符串，例如 [{"Key":"env","Value":"prod"}]
            resource_arns: 资源 ARN 列表（最多 50 个）
            category: Custom / System / All，默认 All
            page_size: 每页条数
            next_token: 分页令牌
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        if not tags and not resource_arns:
            raise ValueError("必须提供 tags 或 resource_arns 之一（阿里云 ListTagResources 约束）")

        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_tag_client(account, rid)
        req = tag_models.ListTagResourcesRequest(
            region_id=rid,
            tags=tags,
            resource_arn=resource_arns,
            category=category,
            page_size=page_size,
            next_token=next_token,
        )
        resp = client.list_tag_resources_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_instances(
        account: str,
        region: Optional[str] = None,
        vpc_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        instance_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 ECS 实例（DescribeInstances，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            vpc_id: 按 VPC 过滤
            security_group_id: 按安全组过滤
            instance_ids: 实例 ID 列表
            page_number: 页码
            page_size: 每页条数
            next_token: 分页令牌（与 Page 方式二选一，以 API 支持为准）
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_ecs_client(account, rid)
        ids_str = json.dumps(instance_ids) if instance_ids else None
        req = ecs_models.DescribeInstancesRequest(
            region_id=rid,
            vpc_id=vpc_id,
            security_group_id=security_group_id,
            instance_ids=ids_str,
            page_number=page_number,
            page_size=page_size,
            next_token=next_token,
        )
        resp = client.describe_instances_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_disks(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        disk_ids: Optional[List[str]] = None,
        disk_type: Optional[str] = None,
        status: Optional[str] = None,
        auto_snapshot_policy_id: Optional[str] = None,
        enable_automated_snapshot_policy: Optional[bool] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        查询 ECS 云盘列表与快照策略绑定字段（DescribeDisks，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ecs_client(account, rid)
        req = ecs_models.DescribeDisksRequest(
            region_id=rid,
            instance_id=instance_id,
            disk_ids=json.dumps(disk_ids) if disk_ids else None,
            disk_type=disk_type,
            status=status,
            auto_snapshot_policy_id=auto_snapshot_policy_id,
            enable_automated_snapshot_policy=enable_automated_snapshot_policy,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
            next_token=next_token,
            max_results=max_results,
        )
        resp = client.describe_disks_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_snapshots(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        disk_id: Optional[str] = None,
        snapshot_ids: Optional[List[str]] = None,
        snapshot_name: Optional[str] = None,
        snapshot_type: Optional[str] = None,
        status: Optional[str] = None,
        source_disk_type: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        查询 ECS 快照列表（DescribeSnapshots，只读），可按实例、云盘、快照类型过滤。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ecs_client(account, rid)
        req = ecs_models.DescribeSnapshotsRequest(
            region_id=rid,
            instance_id=instance_id,
            disk_id=disk_id,
            snapshot_ids=json.dumps(snapshot_ids) if snapshot_ids else None,
            snapshot_name=snapshot_name,
            snapshot_type=snapshot_type,
            status=status,
            source_disk_type=source_disk_type,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
            next_token=next_token,
            max_results=max_results,
        )
        resp = client.describe_snapshots_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_auto_snapshot_policies(
        account: str,
        region: Optional[str] = None,
        auto_snapshot_policy_id: Optional[str] = None,
        auto_snapshot_policy_name: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        查询 ECS 自动快照策略详情（DescribeAutoSnapshotPolicyEx，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ecs_client(account, rid)
        req = ecs_models.DescribeAutoSnapshotPolicyExRequest(
            region_id=rid,
            auto_snapshot_policy_id=auto_snapshot_policy_id,
            auto_snapshot_policy_name=auto_snapshot_policy_name,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_auto_snapshot_policy_ex_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_auto_snapshot_policy_associations(
        account: str,
        region: Optional[str] = None,
        auto_snapshot_policy_id: Optional[str] = None,
        disk_id: Optional[str] = None,
        max_results: int = 50,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 ECS 自动快照策略与云盘的绑定关系（DescribeAutoSnapshotPolicyAssociations，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        if auto_snapshot_policy_id and disk_id:
            raise ValueError("auto_snapshot_policy_id 与 disk_id 只能指定一个")
        rid = _get_region(account, region)
        client = get_ecs_client(account, rid)
        req = ecs_models.DescribeAutoSnapshotPolicyAssociationsRequest(
            region_id=rid,
            auto_snapshot_policy_id=auto_snapshot_policy_id,
            disk_id=disk_id,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.describe_auto_snapshot_policy_associations_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_security_groups(
        account: str,
        region: Optional[str] = None,
        vpc_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        security_group_name: Optional[str] = None,
        security_group_ids: Optional[List[str]] = None,
        security_group_type: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        列举安全组（DescribeSecurityGroups，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            vpc_id: 按 VPC 过滤
            security_group_id: 按单个安全组 ID 过滤
            security_group_name: 按安全组名称过滤
            security_group_ids: 多个安全组 ID 列表（最多 100 个）
            security_group_type: normal 或 enterprise
            resource_group_id: 按资源组过滤
            page_number / page_size: 传统分页参数
            next_token / max_results: Token 分页参数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_ecs_client(account, rid)
        security_group_ids_str = json.dumps(security_group_ids) if security_group_ids else None
        req = ecs_models.DescribeSecurityGroupsRequest(
            region_id=rid,
            vpc_id=vpc_id,
            security_group_id=security_group_id,
            security_group_name=security_group_name,
            security_group_ids=security_group_ids_str,
            security_group_type=security_group_type,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
            next_token=next_token,
            max_results=max_results,
        )
        resp = client.describe_security_groups_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_security_group_attribute(
        account: str,
        security_group_id: str,
        region: Optional[str] = None,
        direction: str = "all",
        nic_type: Optional[str] = None,
        max_results: int = 500,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询安全组详细属性与规则（DescribeSecurityGroupAttribute，只读）。

        参数:
            account: 账号标识（必填）
            security_group_id: 安全组 ID（必填）
            region: 区域，默认账号默认区域
            direction: ingress / egress / all
            nic_type: VPC 场景通常为 intranet
            max_results: 每页条数，10-1000
            next_token: 分页令牌
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_ecs_client(account, rid)
        req = ecs_models.DescribeSecurityGroupAttributeRequest(
            region_id=rid,
            security_group_id=security_group_id,
            direction=direction,
            nic_type=nic_type,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.describe_security_group_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_find_public_security_group_rules(
        account: str,
        region: Optional[str] = None,
        vpc_id: Optional[str] = None,
        security_group_ids: Optional[List[str]] = None,
        direction: str = "ingress",
        target_cidrs: Optional[List[str]] = None,
        include_egress: bool = False,
        page_size: int = 100,
        max_groups: int = 500,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        """
        聚合扫描安全组中对公网开放的规则，避免模型逐个安全组反复调用详情接口。

        默认检查入方向 0.0.0.0/0 与 ::/0；如需出方向规则，设置 include_egress=true。
        返回命中的规则摘要，不返回完整 OpenAPI 响应体。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        if direction not in {"ingress", "egress", "all"}:
            raise ValueError("direction 必须为 ingress、egress 或 all")

        rid = _get_region(account, region)
        client = get_ecs_client(account, rid)
        cidrs = set(target_cidrs or ["0.0.0.0/0", "::/0"])
        list_page_size = max(1, min(page_size, 100))
        group_limit = max(1, max_groups)
        worker_count = max(1, min(max_workers, 16))

        groups: List[Dict[str, Any]] = []
        if security_group_ids:
            ids_str = json.dumps(security_group_ids)
            req = ecs_models.DescribeSecurityGroupsRequest(
                region_id=rid,
                security_group_ids=ids_str,
                page_number=1,
                page_size=min(len(security_group_ids), 100),
            )
            resp = client.describe_security_groups_with_options(req, get_runtime_options())
            groups.extend(_security_group_items(openapi_response_to_dict(resp).get("body", {})))
        else:
            page_number = 1
            total_count: Optional[int] = None
            while len(groups) < group_limit:
                req = ecs_models.DescribeSecurityGroupsRequest(
                    region_id=rid,
                    vpc_id=vpc_id,
                    page_number=page_number,
                    page_size=list_page_size,
                )
                resp = client.describe_security_groups_with_options(req, get_runtime_options())
                body = openapi_response_to_dict(resp).get("body", {})
                page_items = _security_group_items(body)
                groups.extend(page_items)
                total_count = body.get("TotalCount", total_count)
                if not page_items or (total_count is not None and page_number * list_page_size >= int(total_count)):
                    break
                page_number += 1

        groups = groups[:group_limit]
        scan_direction = "all" if include_egress else direction

        def scan_group(group: Dict[str, Any]) -> Dict[str, Any]:
            security_group_id = group.get("SecurityGroupId")
            if not security_group_id:
                return {"matches": [], "error": "安全组缺少 SecurityGroupId"}

            matches: List[Dict[str, Any]] = []
            next_token = None
            while True:
                req = ecs_models.DescribeSecurityGroupAttributeRequest(
                    region_id=rid,
                    security_group_id=security_group_id,
                    direction=scan_direction,
                    max_results=1000,
                    next_token=next_token,
                )
                resp = get_ecs_client(account, rid).describe_security_group_attribute_with_options(req, get_runtime_options())
                body = openapi_response_to_dict(resp).get("body", {})
                for rule in _permission_items(body):
                    rule_direction = str(rule.get("Direction") or scan_direction).lower()
                    if not include_egress and rule_direction == "egress":
                        continue
                    if direction != "all" and rule_direction not in {direction, "all"}:
                        continue
                    if str(rule.get("Policy") or "Accept").lower() not in {"accept", "allow"}:
                        continue
                    matched_cidrs = sorted(cidrs.intersection(_rule_cidrs(rule)))
                    if not matched_cidrs:
                        continue
                    matches.append(
                        {
                            "security_group_id": security_group_id,
                            "security_group_name": group.get("SecurityGroupName"),
                            "vpc_id": group.get("VpcId"),
                            "direction": rule_direction,
                            "policy": rule.get("Policy"),
                            "ip_protocol": rule.get("IpProtocol"),
                            "port_range": rule.get("PortRange"),
                            "matched_cidrs": matched_cidrs,
                            "priority": rule.get("Priority"),
                            "nic_type": rule.get("NicType"),
                            "description": rule.get("Description"),
                            "source_group_id": rule.get("SourceGroupId"),
                            "rule_id": rule.get("SecurityGroupRuleId"),
                        }
                    )
                next_token = body.get("NextToken")
                if not next_token:
                    break
            return {"matches": matches, "error": None}

        matches: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_group = {executor.submit(scan_group, group): group for group in groups}
            for future in as_completed(future_to_group):
                group = future_to_group[future]
                try:
                    result = future.result()
                except Exception as exc:
                    errors.append(
                        {
                            "security_group_id": group.get("SecurityGroupId"),
                            "security_group_name": group.get("SecurityGroupName"),
                            "error": str(exc),
                        }
                    )
                    continue
                if result.get("error"):
                    errors.append(
                        {
                            "security_group_id": group.get("SecurityGroupId"),
                            "security_group_name": group.get("SecurityGroupName"),
                            "error": result["error"],
                        }
                    )
                matches.extend(result.get("matches", []))

        matches.sort(key=lambda item: (str(item.get("security_group_id") or ""), str(item.get("port_range") or "")))
        return {
            "account": account,
            "region": rid,
            "vpc_id": vpc_id,
            "target_cidrs": sorted(cidrs),
            "direction": scan_direction,
            "scanned_security_group_count": len(groups),
            "matched_rule_count": len(matches),
            "has_public_open_rules": bool(matches),
            "truncated_by_max_groups": len(groups) >= group_limit and not security_group_ids,
            "matches": matches,
            "errors": errors,
            "message": "发现公网开放规则" if matches else "未发现匹配的公网开放规则",
        }

    @mcp.tool()
    def aliyun_describe_rds_instances(
        account: str,
        region: Optional[str] = None,
        dbinstance_id: Optional[str] = None,
        engine: Optional[str] = None,
        dbinstance_status: Optional[str] = None,
        search_key: Optional[str] = None,
        vpc_id: Optional[str] = None,
        v_switch_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 30,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 RDS 实例（DescribeDBInstances，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            dbinstance_id: 按单个实例 ID 过滤
            engine: MySQL / PostgreSQL / SQLServer / MariaDB
            dbinstance_status: 按实例状态过滤
            search_key: 模糊搜索实例 ID 或描述
            vpc_id / v_switch_id: 按网络过滤
            resource_group_id: 按资源组过滤
            page_number / page_size: 传统分页参数
            max_results / next_token: Token 分页参数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_rds_client(account, rid)
        req = rds_models.DescribeDBInstancesRequest(
            region_id=rid,
            dbinstance_id=dbinstance_id,
            engine=engine,
            dbinstance_status=dbinstance_status,
            search_key=search_key,
            vpc_id=vpc_id,
            v_switch_id=v_switch_id,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.describe_dbinstances_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_rds_instance_attribute(
        account: str,
        dbinstance_id: str,
    ) -> Dict[str, Any]:
        """
        查询单个 RDS 实例详情（DescribeDBInstanceAttribute，只读）。

        参数:
            account: 账号标识（必填）
            dbinstance_id: RDS 实例 ID（必填）
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_rds_client(account, None)
        req = rds_models.DescribeDBInstanceAttributeRequest(
            dbinstance_id=dbinstance_id,
        )
        resp = client.describe_dbinstance_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_redis_instances(
        account: str,
        region: Optional[str] = None,
        instance_ids: Optional[List[str]] = None,
        instance_status: Optional[str] = None,
        instance_type: Optional[str] = None,
        search_key: Optional[str] = None,
        architecture_type: Optional[str] = None,
        vpc_id: Optional[str] = None,
        v_switch_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        """
        列举 Redis/Tair 实例（DescribeInstances，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_kvstore_client(account, rid)
        req = kv_models.DescribeInstancesRequest(
            region_id=rid,
            instance_ids=",".join(instance_ids) if instance_ids else None,
            instance_status=instance_status,
            instance_type=instance_type,
            search_key=search_key,
            architecture_type=architecture_type,
            vpc_id=vpc_id,
            v_switch_id=v_switch_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_instances_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_redis_instance_attribute(
        account: str,
        instance_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询单个 Redis/Tair 实例详情（DescribeInstanceAttribute，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_kvstore_client(account, rid)
        req = kv_models.DescribeInstanceAttributeRequest(instance_id=instance_id)
        resp = client.describe_instance_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_mongodb_instances(
        account: str,
        region: Optional[str] = None,
        dbinstance_id: Optional[str] = None,
        dbinstance_description: Optional[str] = None,
        dbinstance_status: Optional[str] = None,
        engine_version: Optional[str] = None,
        vpc_id: Optional[str] = None,
        v_switch_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        """
        列举 MongoDB 实例（DescribeDBInstances，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_dds_client(account, rid)
        req = dds_models.DescribeDBInstancesRequest(
            region_id=rid,
            dbinstance_id=dbinstance_id,
            dbinstance_description=dbinstance_description,
            dbinstance_status=dbinstance_status,
            engine="MongoDB",
            engine_version=engine_version,
            vpc_id=vpc_id,
            v_switch_id=v_switch_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_dbinstances_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_mongodb_instance_attribute(
        account: str,
        dbinstance_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询单个 MongoDB 实例详情（DescribeDBInstanceAttribute，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_dds_client(account, rid)
        req = dds_models.DescribeDBInstanceAttributeRequest(dbinstance_id=dbinstance_id)
        resp = client.describe_dbinstance_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_load_balancers(
        account: str,
        region: Optional[str] = None,
        load_balancer_id: Optional[str] = None,
        load_balancer_name: Optional[str] = None,
        load_balancer_status: Optional[str] = None,
        address_type: Optional[str] = None,
        network_type: Optional[str] = None,
        vpc_id: Optional[str] = None,
        v_switch_id: Optional[str] = None,
        server_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        """
        列举 CLB 实例（DescribeLoadBalancers，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            load_balancer_id / load_balancer_name: 按实例 ID 或名称过滤
            load_balancer_status: active / inactive / locked
            address_type: internet / intranet
            network_type: vpc / Classic
            vpc_id / v_switch_id: 按网络过滤
            server_id: 按后端 ECS 过滤
            resource_group_id: 按资源组过滤
            page_number / page_size: 分页参数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_slb_client(account, rid)
        req = slb_models.DescribeLoadBalancersRequest(
            region_id=rid,
            load_balancer_id=load_balancer_id,
            load_balancer_name=load_balancer_name,
            load_balancer_status=load_balancer_status,
            address_type=address_type,
            network_type=network_type,
            vpc_id=vpc_id,
            v_switch_id=v_switch_id,
            server_id=server_id,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_load_balancers_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_alb_load_balancers(
        account: str,
        region: Optional[str] = None,
        load_balancer_ids: Optional[List[str]] = None,
        load_balancer_names: Optional[List[str]] = None,
        address_type: Optional[str] = None,
        load_balancer_status: Optional[str] = None,
        vpc_ids: Optional[List[str]] = None,
        resource_group_id: Optional[str] = None,
        max_results: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 ALB 实例（ListLoadBalancers，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_alb_client(account, rid)
        req = alb_models.ListLoadBalancersRequest(
            load_balancer_ids=load_balancer_ids,
            load_balancer_names=load_balancer_names,
            address_type=address_type,
            load_balancer_status=load_balancer_status,
            vpc_ids=vpc_ids,
            resource_group_id=resource_group_id,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.list_load_balancers_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_get_alb_load_balancer_attribute(
        account: str,
        load_balancer_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 ALB 实例详情（GetLoadBalancerAttribute，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_alb_client(account, rid)
        req = alb_models.GetLoadBalancerAttributeRequest(load_balancer_id=load_balancer_id)
        resp = client.get_load_balancer_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_alb_listeners(
        account: str,
        region: Optional[str] = None,
        load_balancer_ids: Optional[List[str]] = None,
        listener_protocol: Optional[str] = None,
        listener_ids: Optional[List[str]] = None,
        max_results: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 ALB 监听（ListListeners，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_alb_client(account, rid)
        req = alb_models.ListListenersRequest(
            load_balancer_ids=load_balancer_ids,
            listener_protocol=listener_protocol,
            listener_ids=listener_ids,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.list_listeners_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_get_alb_listener_attribute(
        account: str,
        listener_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 ALB 监听详情（GetListenerAttribute，只读），HTTPS 监听会返回 Certificates 中的证书 ID。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_alb_client(account, rid)
        req = alb_models.GetListenerAttributeRequest(listener_id=listener_id)
        resp = client.get_listener_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ssl_certificate_orders(
        account: str,
        region: Optional[str] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        cert_type: Optional[str] = None,
        current_page: int = 1,
        show_size: int = 50,
    ) -> Dict[str, Any]:
        """
        查询 SSL 证书订单列表（CAS ListUserCertificateOrder，只读），用于查看证书名称、ID、状态与到期信息。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cas20200407 import models as cas_models
        except ImportError as e:
            raise ValueError("SSL 证书查询需要依赖 alibabacloud_cas20200407，请先安装 requirements.txt。") from e

        rid, client = _get_cas_client(account, region)
        req = cas_models.ListUserCertificateOrderRequest()
        _set_if_present(req, "keyword", keyword)
        _set_if_present(req, "status", status)
        _set_if_present(req, "order_type", order_type)
        _set_if_present(req, "cert_type", cert_type)
        _set_if_present(req, "current_page", current_page)
        _set_if_present(req, "show_size", show_size)
        resp = client.list_user_certificate_order_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_ssl_certificates(
        account: str,
        region: Optional[str] = None,
        keyword: Optional[str] = None,
        certificate_status: Optional[str] = None,
        certificate_source: Optional[str] = None,
        instance_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        current_page: int = 1,
        show_size: int = 50,
    ) -> Dict[str, Any]:
        """
        查询 SSL/CAS v2 证书列表（CAS ListCertificates，只读），包含 v2 证书及 NotAfter/NotBefore 到期字段。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cas20200407 import models as cas_models
        except ImportError as e:
            raise ValueError("SSL 证书查询需要依赖 alibabacloud_cas20200407，请先安装 requirements.txt。") from e

        rid, client = _get_cas_client(account, region)
        req = cas_models.ListCertificatesRequest(
            certificate_source=certificate_source,
            certificate_status=certificate_status,
            current_page=current_page,
            instance_id=instance_id,
            keyword=keyword,
            resource_group_id=resource_group_id,
            show_size=show_size,
        )
        resp = client.list_certificates_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        result["api"] = "ListCertificates"
        result["note"] = "SSL/CAS v2 certificate list; CertificateList items include NotAfter/NotBefore when returned by CAS."
        return result

    @mcp.tool()
    def aliyun_describe_ssl_certificate_state(
        account: str,
        certificate_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 SSL 证书状态（CAS DescribeCertificateState，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cas20200407 import models as cas_models
        except ImportError as e:
            raise ValueError("SSL 证书查询需要依赖 alibabacloud_cas20200407，请先安装 requirements.txt。") from e

        rid, client = _get_cas_client(account, region)
        req = cas_models.DescribeCertificateStateRequest()
        for field_name in ["certificate_id", "cert_id", "order_id"]:
            _set_if_present(req, field_name, certificate_id)
        resp = client.describe_certificate_state_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_nlb_load_balancers(
        account: str,
        region: Optional[str] = None,
        load_balancer_ids: Optional[List[str]] = None,
        load_balancer_names: Optional[List[str]] = None,
        address_type: Optional[str] = None,
        load_balancer_status: Optional[str] = None,
        vpc_ids: Optional[List[str]] = None,
        resource_group_id: Optional[str] = None,
        max_results: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 NLB 实例（ListLoadBalancers，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_nlb_client(account, rid)
        req = nlb_models.ListLoadBalancersRequest(
            region_id=rid,
            load_balancer_ids=load_balancer_ids,
            load_balancer_names=load_balancer_names,
            address_type=address_type,
            load_balancer_status=load_balancer_status,
            vpc_ids=vpc_ids,
            resource_group_id=resource_group_id,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.list_load_balancers_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_get_nlb_load_balancer_attribute(
        account: str,
        load_balancer_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 NLB 实例详情（GetLoadBalancerAttribute，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_nlb_client(account, rid)
        req = nlb_models.GetLoadBalancerAttributeRequest(load_balancer_id=load_balancer_id)
        resp = client.get_load_balancer_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_nlb_listeners(
        account: str,
        region: Optional[str] = None,
        load_balancer_ids: Optional[List[str]] = None,
        listener_protocol: Optional[str] = None,
        listener_ids: Optional[List[str]] = None,
        max_results: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 NLB 监听（ListListeners，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_nlb_client(account, rid)
        req = nlb_models.ListListenersRequest(
            load_balancer_ids=load_balancer_ids,
            listener_protocol=listener_protocol,
            listener_ids=listener_ids,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.list_listeners_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_load_balancer_attribute(
        account: str,
        load_balancer_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询单个 CLB 实例详情（DescribeLoadBalancerAttribute，只读）。

        参数:
            account: 账号标识（必填）
            load_balancer_id: CLB 实例 ID（必填）
            region: 区域，默认账号默认区域
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_slb_client(account, rid)
        req = slb_models.DescribeLoadBalancerAttributeRequest(
            region_id=rid,
            load_balancer_id=load_balancer_id,
        )
        resp = client.describe_load_balancer_attribute_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_load_balancer_listeners(
        account: str,
        region: Optional[str] = None,
        load_balancer_ids: Optional[List[str]] = None,
        listener_port: Optional[int] = None,
        listener_protocol: Optional[str] = None,
        description: Optional[str] = None,
        max_results: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 CLB 监听列表（DescribeLoadBalancerListeners，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            load_balancer_ids: CLB 实例 ID 列表，最多 10 个
            listener_port: 按监听端口过滤
            listener_protocol: tcp / udp / http / https
            description: 按监听描述过滤
            max_results: 每次返回条数，1-100
            next_token: 分页令牌
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_slb_client(account, rid)
        req = slb_models.DescribeLoadBalancerListenersRequest(
            region_id=rid,
            load_balancer_id=load_balancer_ids,
            listener_port=listener_port,
            listener_protocol=listener_protocol,
            description=description,
            max_results=max_results,
            next_token=next_token,
        )
        resp = client.describe_load_balancer_listeners_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_slb_health_status(
        account: str,
        load_balancer_id: str,
        region: Optional[str] = None,
        listener_port: Optional[int] = None,
        listener_protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 CLB 后端健康状态（DescribeHealthStatus，只读）。

        参数:
            account: 账号标识（必填）
            load_balancer_id: CLB 实例 ID（必填）
            region: 区域，默认账号默认区域
            listener_port: 前端监听端口
            listener_protocol: 监听协议
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_slb_client(account, rid)
        req = slb_models.DescribeHealthStatusRequest(
            region_id=rid,
            load_balancer_id=load_balancer_id,
            listener_port=listener_port,
            listener_protocol=listener_protocol,
        )
        resp = client.describe_health_status_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_eip_addresses(
        account: str,
        region: Optional[str] = None,
        allocation_id: Optional[str] = None,
        associated_instance_id: Optional[str] = None,
        associated_instance_type: Optional[str] = None,
        eip_address: Optional[str] = None,
        status: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 EIP（DescribeEipAddresses，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeEipAddressesRequest(
            region_id=rid,
            allocation_id=allocation_id,
            associated_instance_id=associated_instance_id,
            associated_instance_type=associated_instance_type,
            eip_address=eip_address,
            status=status,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_eip_addresses_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_cloud_firewall_assets(
        account: str,
        region: Optional[str] = None,
        current_page: int = 1,
        page_size: int = 50,
        search_item: Optional[str] = None,
        resource_type: Optional[str] = None,
        protect_status: Optional[str] = None,
        status: Optional[str] = None,
        member_uid: Optional[int] = None,
        region_no: Optional[str] = None,
        ip_version: Optional[str] = None,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """
        查询云防火墙资产列表（Cloud Firewall DescribeAssetList，只读），用于查看公网资产是否已纳入防护。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cloudfw20171207 import models as cloudfw_models
        except ImportError as e:
            raise ValueError("云防火墙查询需要依赖 alibabacloud_cloudfw20171207，请先安装 requirements.txt。") from e

        rid, client = _get_cloudfw_client(account, region)
        if not hasattr(client, "describe_asset_list_with_options"):
            raise ValueError("当前 alibabacloud_cloudfw20171207 版本不支持 DescribeAssetList，请升级 requirements.txt 依赖。")
        req = cloudfw_models.DescribeAssetListRequest()
        _set_if_present(req, "current_page", str(current_page))
        _set_if_present(req, "page_size", str(min(max(page_size, 1), 50)))
        _set_if_present(req, "search_item", search_item)
        _set_if_present(req, "resource_type", resource_type)
        _set_if_present(req, "status", status or protect_status)
        _set_if_present(req, "member_uid", member_uid)
        _set_if_present(req, "region_no", region_no)
        _set_if_present(req, "ip_version", ip_version)
        _set_if_present(req, "lang", lang)
        resp = client.describe_asset_list_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        result["api"] = "DescribeAssetList"
        result["note"] = "云防火墙资产列表，可按返回字段中的 ProtectStatus/Status 等判断公网 IP 是否已添加防护。"
        return result

    @mcp.tool()
    def aliyun_get_cloud_firewall_public_ip_protection_status(
        account: str,
        region: Optional[str] = None,
        search_item: Optional[str] = None,
        resource_type: Optional[str] = None,
        member_uid: Optional[int] = None,
        page_size: int = 50,
        max_pages: int = 5,
        include_raw: bool = False,
    ) -> Dict[str, Any]:
        """
        汇总云防火墙公网 IP 防护状态，将资产按已防护、未防护、未知状态分组。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cloudfw20171207 import models as cloudfw_models
        except ImportError as e:
            raise ValueError("云防火墙查询需要依赖 alibabacloud_cloudfw20171207，请先安装 requirements.txt。") from e

        rid, client = _get_cloudfw_client(account, region)
        if not hasattr(client, "describe_asset_list_with_options"):
            raise ValueError("当前 alibabacloud_cloudfw20171207 版本不支持 DescribeAssetList，请升级 requirements.txt 依赖。")

        protected: List[Dict[str, Any]] = []
        unprotected: List[Dict[str, Any]] = []
        unknown: List[Dict[str, Any]] = []
        raw_pages: List[Dict[str, Any]] = []
        effective_page_size = min(max(page_size, 1), 50)

        for page in range(1, max(1, max_pages) + 1):
            req = cloudfw_models.DescribeAssetListRequest()
            _set_if_present(req, "current_page", str(page))
            _set_if_present(req, "page_size", str(effective_page_size))
            _set_if_present(req, "search_item", search_item)
            _set_if_present(req, "resource_type", resource_type)
            _set_if_present(req, "member_uid", member_uid)
            resp = client.describe_asset_list_with_options(req, get_runtime_options())
            result = openapi_response_to_dict(resp)
            if include_raw:
                raw_pages.append(result)

            items = _collect_cloudfw_asset_items(result)
            if not items:
                break
            for item in items:
                public_ip = _first_present(item, _PUBLIC_IP_KEYS)
                if not public_ip:
                    continue
                protection_value = _first_present(item, _PROTECTION_KEYS)
                normalized = {
                    "public_ip": public_ip,
                    "protection_status": protection_value,
                    "asset_type": _first_present(item, ["AssetType", "ResourceType", "Type", "InstanceType"]),
                    "instance_id": _first_present(item, ["ResourceInstanceId", "BindInstanceId", "InstanceId", "ResourceId", "AssetId"]),
                    "instance_name": _first_present(item, ["Name", "BindInstanceName", "InstanceName", "ResourceName"]),
                    "region": _first_present(item, ["RegionID", "Region", "RegionNo", "RegionId"]),
                    "raw": item if include_raw else None,
                }
                group = _classify_cloudfw_protection(protection_value)
                if group == "protected":
                    protected.append(normalized)
                elif group == "unprotected":
                    unprotected.append(normalized)
                else:
                    unknown.append(normalized)

            if len(items) < effective_page_size:
                break

        response: Dict[str, Any] = {
            "account": account,
            "region": rid,
            "api": "DescribeAssetList",
            "summary": {
                "protected_public_ip_count": len(protected),
                "unprotected_public_ip_count": len(unprotected),
                "unknown_status_public_ip_count": len(unknown),
            },
            "protected_public_ips": protected,
            "unprotected_public_ips": unprotected,
            "unknown_status_public_ips": unknown,
            "note": "不同云防火墙版本返回字段可能不同；如分类为 unknown，请查看 protection_status 或 include_raw=true 的原始字段。",
        }
        if include_raw:
            response["raw_pages"] = raw_pages
        return response

    @mcp.tool()
    def aliyun_describe_cloud_firewall_traffic_log(
        account: str,
        start_time: str,
        end_time: str,
        region: Optional[str] = None,
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        src_port: Optional[str] = None,
        dst_port: Optional[str] = None,
        direction: Optional[str] = None,
        firewall_type: str = "InternetFirewall",
        flow_type: Optional[str] = None,
        ip_protocol: Optional[str] = None,
        ip_version: str = "4",
        rule_result: Optional[str] = None,
        rule_id: Optional[str] = None,
        domain_name: Optional[str] = None,
        domain_url: Optional[str] = None,
        app_id: Optional[str] = None,
        member_uid: Optional[int] = None,
        source_code: str = "yundun",
        current_page: int = 1,
        page_size: int = 20,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """
        查询云防火墙日志审计流量日志（DescribeTrafficLog，只读），用于按源 IP、目的 IP、端口、方向等过滤访问记录。

        参数:
            account: 账号标识（必填）
            start_time / end_time: Unix 秒/毫秒时间戳或 ISO8601；云防火墙接口仅支持 7 日内数据，建议单次不超过 1 天
            src_ip / dst_ip: 源 IP / 目的 IP
            src_port / dst_port: 源端口 / 目的端口，例如 dst_port="3389"
            direction: in 或 out
            firewall_type: InternetFirewall、VpcFirewall、NatFirewall 或 DnsFirewall，默认 InternetFirewall
            flow_type: UnidirectionalFlow 或 BidirectionalFlow
            rule_result: 0 放行、1 拒绝、2 观察
            source_code: API 溯源码，默认 yundun
            current_page / page_size: 分页，page_size 最大 20
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        try:
            from alibabacloud_cloudfw20171207 import models as cloudfw_models
        except ImportError as e:
            raise ValueError("云防火墙查询需要依赖 alibabacloud_cloudfw20171207，请先安装 requirements.txt。") from e

        rid, client = _get_cloudfw_client(account, region)
        if not hasattr(client, "describe_traffic_log_with_options"):
            raise ValueError("当前 alibabacloud_cloudfw20171207 版本不支持 DescribeTrafficLog，请升级 requirements.txt 依赖。")

        start = str(_parse_sls_time(start_time))
        end = str(_parse_sls_time(end_time))
        if int(end) <= int(start):
            raise ValueError("end_time 必须晚于 start_time")
        effective_page_size = str(min(max(page_size, 1), 20))
        req = cloudfw_models.DescribeTrafficLogRequest(
            start_time=start,
            end_time=end,
            source_code=source_code,
            current_page=str(max(current_page, 1)),
            page_size=effective_page_size,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            direction=direction,
            firewall_type=firewall_type,
            flow_type=flow_type,
            ip_protocol=ip_protocol,
            ip_version=ip_version,
            rule_result=rule_result,
            rule_id=rule_id,
            domain_name=domain_name,
            domain_url=domain_url,
            app_id=app_id,
            member_uid=member_uid,
            lang=lang,
        )
        resp = client.describe_traffic_log_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        items = _cloudfw_body_items(result)
        source_ip_counts = Counter(str(item.get("SrcIP")) for item in items if item.get("SrcIP"))
        result["region"] = rid
        result["api"] = "DescribeTrafficLog"
        result["filters"] = {
            "start_time": start,
            "end_time": end,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": src_port,
            "dst_port": dst_port,
            "direction": direction,
            "firewall_type": firewall_type,
            "flow_type": flow_type,
            "ip_protocol": ip_protocol,
            "rule_result": rule_result,
            "member_uid": member_uid,
            "current_page": max(current_page, 1),
            "page_size": int(effective_page_size),
        }
        result["source_ip_summary"] = [
            {"src_ip": src_ip_value, "count": count}
            for src_ip_value, count in source_ip_counts.most_common()
        ]
        result["note"] = "对应云防火墙控制台 日志审计 > 流量日志。接口仅支持 7 日内数据，建议单次查询不超过 1 天；page_size 最大 20。"
        return result

    @mcp.tool()
    def aliyun_describe_nat_gateways(
        account: str,
        region: Optional[str] = None,
        nat_gateway_id: Optional[str] = None,
        name: Optional[str] = None,
        network_type: Optional[str] = None,
        status: Optional[str] = None,
        vpc_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 NAT 网关（DescribeNatGateways，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeNatGatewaysRequest(
            region_id=rid,
            nat_gateway_id=nat_gateway_id,
            name=name,
            network_type=network_type,
            status=status,
            vpc_id=vpc_id,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_nat_gateways_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_route_tables(
        account: str,
        region: Optional[str] = None,
        route_table_id: Optional[str] = None,
        route_table_name: Optional[str] = None,
        route_table_type: Optional[str] = None,
        vpc_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举路由表（DescribeRouteTableList，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeRouteTableListRequest(
            region_id=rid,
            route_table_id=route_table_id,
            route_table_name=route_table_name,
            route_table_type=route_table_type,
            vpc_id=vpc_id,
            resource_group_id=resource_group_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_route_table_list_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_route_entries(
        account: str,
        route_table_id: str,
        region: Optional[str] = None,
        route_entry_id: Optional[str] = None,
        route_entry_name: Optional[str] = None,
        route_entry_type: Optional[str] = None,
        destination_cidr_block: Optional[str] = None,
        next_hop_type: Optional[str] = None,
        next_hop_id: Optional[str] = None,
        max_result: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举路由条目（DescribeRouteEntryList，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeRouteEntryListRequest(
            region_id=rid,
            route_table_id=route_table_id,
            route_entry_id=route_entry_id,
            route_entry_name=route_entry_name,
            route_entry_type=route_entry_type,
            destination_cidr_block=destination_cidr_block,
            next_hop_type=next_hop_type,
            next_hop_id=next_hop_id,
            max_result=max_result,
            next_token=next_token,
        )
        resp = client.describe_route_entry_list_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_ack_clusters(
        account: str,
        region: Optional[str] = None,
        cluster_id: Optional[str] = None,
        name: Optional[str] = None,
        cluster_type: Optional[str] = None,
        profile: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 ACK 集群（DescribeClustersV1，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_cs_client(account, rid)
        req = cs_models.DescribeClustersV1Request(
            cluster_id=cluster_id,
            name=name,
            cluster_type=cluster_type,
            profile=profile,
            region_id=rid,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_clusters_v1_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_sls_projects(
        account: str,
        region: Optional[str] = None,
        project_name: Optional[str] = None,
        offset: int = 0,
        size: int = 100,
    ) -> Dict[str, Any]:
        """
        列举 SLS Project（基于 aliyun-log-python-sdk，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid, client = _get_sls_client(account, region)
        projects = client.list_project(offset=offset, size=size)
        items = []
        for item in projects:
            name = item if isinstance(item, str) else getattr(item, "project_name", None) or str(item)
            if project_name and project_name not in name:
                continue
            items.append(name)
        return {"region": rid, "count": len(items), "projects": items}

    @mcp.tool()
    def aliyun_list_sls_logstores(
        account: str,
        project_name: str,
        region: Optional[str] = None,
        offset: int = 0,
        size: int = 100,
    ) -> Dict[str, Any]:
        """
        列举指定 SLS Project 下的 Logstore（基于 aliyun-log-python-sdk，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid, client = _get_sls_client(account, region)
        logstores = client.list_logstores(project_name, offset=offset, size=size)
        return {"region": rid, "project_name": project_name, "count": len(logstores), "logstores": list(logstores)}

    @mcp.tool()
    def aliyun_query_sls_logs(
        account: str,
        project_name: str,
        logstore: str,
        from_time: str,
        to_time: str,
        region: Optional[str] = None,
        query: str = "*",
        topic: str = "",
        reverse: bool = False,
        offset: int = 0,
        size: int = 100,
        power_sql: bool = False,
        scan: bool = False,
        forward: bool = False,
        accurate_query: bool = False,
        include_headers: bool = False,
    ) -> Dict[str, Any]:
        """
        查询 SLS Logstore 日志（GetLogs，只读），用于访问日志、流量日志、云防火墙日志等已投递到 SLS 的场景。

        参数:
            account: 账号标识（必填）
            project_name / logstore: SLS Project 与 Logstore
            from_time / to_time: Unix 秒/毫秒时间戳或 ISO8601，如 2026-05-22T00:00:00Z
            query: SLS 查询语句，例如 `dst_port:3389` 或 `* | select src_ip, count(1) group by src_ip`
            topic: 可选 Topic
            reverse: 是否按时间倒序
            offset / size: 分页，size 限制为 1-100
            power_sql / scan / forward / accurate_query: SLS GetLogs 查询选项
            include_headers: 是否返回响应头
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        start = _parse_sls_time(from_time)
        end = _parse_sls_time(to_time)
        if end <= start:
            raise ValueError("to_time 必须晚于 from_time")
        effective_size = min(max(size, 1), 100)
        rid, client = _get_sls_client(account, region)
        resp = client.get_log(
            project_name,
            logstore,
            start,
            end,
            topic=topic,
            query=query,
            reverse=reverse,
            offset=max(offset, 0),
            size=effective_size,
            power_sql=power_sql,
            scan=scan,
            forward=forward,
            accurate_query=accurate_query,
        )
        result: Dict[str, Any] = {
            "region": rid,
            "project_name": project_name,
            "logstore": logstore,
            "from_time": start,
            "to_time": end,
            "query": query,
            "topic": topic,
            "count": resp.get_count(),
            "completed": resp.is_completed(),
            "processed_rows": resp.get_processed_rows(),
            "elapsed_millisecond": resp.get_elapsed_mills(),
            "has_sql": resp.get_has_sql(),
            "where_query": resp.get_where_query(),
            "agg_query": resp.get_agg_query(),
            "logs": [_sls_log_to_dict(item) for item in resp.get_logs()],
            "note": "仅能查询已开启并投递到该 SLS Project/Logstore 的日志；云防火墙访问源 IP 需先确认对应流量/访问日志的 Project 与 Logstore。",
        }
        if hasattr(resp, "get_meta"):
            result["meta"] = resp.get_meta()._to_dict()
        if include_headers:
            result["headers"] = resp.get_all_headers()
        return result

    @mcp.tool()
    def aliyun_describe_vpcs(
        account: str,
        region: Optional[str] = None,
        vpc_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        列举 VPC（DescribeVpcs，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            vpc_id: 按 VPC ID 过滤
            page_number: 页码
            page_size: 每页条数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        from aliyun_mcp.config.accounts import get_account_config

        rid = region or get_account_config(account).default_region
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeVpcsRequest(
            region_id=rid,
            vpc_id=vpc_id,
            page_number=page_number,
            page_size=page_size,
        )
        resp = client.describe_vpcs_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ram_users(
        account: str,
        marker: Optional[str] = None,
        max_items: int = 100,
    ) -> Dict[str, Any]:
        """
        列举 RAM 用户（ListUsers，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_ram_client(account, None)
        req = ram_models.ListUsersRequest(
            marker=marker,
            max_items=max(1, min(max_items, 1000)),
        )
        resp = client.list_users_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ram_roles(
        account: str,
        marker: Optional[str] = None,
        max_items: int = 100,
    ) -> Dict[str, Any]:
        """
        列举 RAM 角色（ListRoles，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_ram_client(account, None)
        req = ram_models.ListRolesRequest(
            marker=marker,
            max_items=max(1, min(max_items, 1000)),
        )
        resp = client.list_roles_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ram_policies(
        account: str,
        policy_type: Optional[str] = None,
        marker: Optional[str] = None,
        max_items: int = 100,
    ) -> Dict[str, Any]:
        """
        列举 RAM 策略（ListPolicies，只读）。

        参数:
            policy_type: System 或 Custom
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_ram_client(account, None)
        req = ram_models.ListPoliciesRequest(
            policy_type=policy_type,
            marker=marker,
            max_items=max(1, min(max_items, 1000)),
        )
        resp = client.list_policies_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ram_access_keys(
        account: str,
        user_name: str,
    ) -> Dict[str, Any]:
        """
        列举指定 RAM 用户 AccessKey 元数据（ListAccessKeys，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_ram_client(account, None)
        req = ram_models.ListAccessKeysRequest(user_name=user_name)
        resp = client.list_access_keys_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_kms_keys(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        列举 KMS 密钥（ListKeys，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_kms_client(account, rid)
        req = kms_models.ListKeysRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 1000)),
        )
        resp = client.list_keys_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_kms_key(
        account: str,
        key_id: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 KMS 密钥详情（DescribeKey，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_kms_client(account, rid)
        req = kms_models.DescribeKeyRequest(key_id=key_id)
        resp = client.describe_key_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_dns_domains(
        account: str,
        page_number: int = 1,
        page_size: int = 20,
        key_word: Optional[str] = None,
        group_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        search_mode: str = "LIKE",
    ) -> Dict[str, Any]:
        """
        列举云解析 DNS 域名（DescribeDomains，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_alidns_client(account, None)
        req = alidns_models.DescribeDomainsRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            key_word=key_word,
            group_id=group_id,
            resource_group_id=resource_group_id,
            search_mode=search_mode,
        )
        resp = client.describe_domains_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_dns_domain_records(
        account: str,
        domain_name: str,
        page_number: int = 1,
        page_size: int = 50,
        rrkey_word: Optional[str] = None,
        type_key_word: Optional[str] = None,
        value_key_word: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举指定域名解析记录（DescribeDomainRecords，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_alidns_client(account, None)
        req = alidns_models.DescribeDomainRecordsRequest(
            domain_name=domain_name,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 500)),
            rrkey_word=rrkey_word,
            type_key_word=type_key_word,
            value_key_word=value_key_word,
            status=status,
        )
        resp = client.describe_domain_records_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_cdn_domains(
        account: str,
        page_number: int = 1,
        page_size: int = 50,
        domain_name: Optional[str] = None,
        domain_status: Optional[str] = None,
        cdn_type: Optional[str] = None,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 CDN 域名（DescribeUserDomains，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_cdn_client(account, None)
        req = cdn_models.DescribeUserDomainsRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 500)),
            domain_name=domain_name,
            domain_status=domain_status,
            cdn_type=cdn_type,
            resource_group_id=resource_group_id,
        )
        resp = client.describe_user_domains_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_dcdn_domains(
        account: str,
        page_number: int = 1,
        page_size: int = 50,
        domain_name: Optional[str] = None,
        domain_status: Optional[str] = None,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 DCDN 域名（DescribeDcdnUserDomains，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_dcdn_client(account, None)
        req = dcdn_models.DescribeDcdnUserDomainsRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 500)),
            domain_name=domain_name,
            domain_status=domain_status,
            resource_group_id=resource_group_id,
        )
        resp = client.describe_dcdn_user_domains_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_describe_cens(
        account: str,
        page_number: int = 1,
        page_size: int = 50,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 CEN 实例（DescribeCens，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        client = get_cbn_client(account, None)
        req = cbn_models.DescribeCensRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 50)),
            resource_group_id=resource_group_id,
        )
        resp = client.describe_cens_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_transit_routers(
        account: str,
        region: Optional[str] = None,
        cen_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        transit_router_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 CEN 转发路由器 TR（ListTransitRouters，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_cbn_client(account, rid)
        req = cbn_models.ListTransitRoutersRequest(
            region_id=rid,
            cen_id=cen_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 50)),
            transit_router_name=transit_router_name,
        )
        resp = client.list_transit_routers_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_vpn_gateways(
        account: str,
        region: Optional[str] = None,
        vpn_gateway_id: Optional[str] = None,
        vpc_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 VPN 网关（DescribeVpnGateways，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeVpnGatewaysRequest(
            region_id=rid,
            vpn_gateway_id=vpn_gateway_id,
            vpc_id=vpc_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            status=status,
        )
        resp = client.describe_vpn_gateways_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_vpn_connections(
        account: str,
        region: Optional[str] = None,
        vpn_gateway_id: Optional[str] = None,
        customer_gateway_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        列举 IPsec VPN 连接（DescribeVpnConnections，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeVpnConnectionsRequest(
            region_id=rid,
            vpn_gateway_id=vpn_gateway_id,
            customer_gateway_id=customer_gateway_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
        )
        resp = client.describe_vpn_connections_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_ssl_vpn_servers(
        account: str,
        region: Optional[str] = None,
        vpn_gateway_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 SSL VPN 服务端（DescribeSslVpnServers，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.DescribeSslVpnServersRequest(
            region_id=rid,
            vpn_gateway_id=vpn_gateway_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            name=name,
        )
        resp = client.describe_ssl_vpn_servers_with_options(req, get_runtime_options())
        return openapi_response_to_dict(resp)

    @mcp.tool()
    def aliyun_list_privatelink_endpoint_services(
        account: str,
        region: Optional[str] = None,
        service_name: Optional[str] = None,
        max_results: int = 50,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举可用的 PrivateLink 终端节点服务（ListVpcEndpointServicesByEndUser，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.ListVpcEndpointServicesByEndUserRequest(
            service_name=service_name,
            max_results=max(1, min(max_results, 100)),
            next_token=next_token,
        )
        resp = client.list_vpc_endpoint_services_by_end_user_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_privatelink_endpoints(
        account: str,
        region: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        endpoint_name: Optional[str] = None,
        max_results: int = 50,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 PrivateLink 终端节点（ListVpcGatewayEndpoints，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_vpc_client(account, rid)
        req = vpc_models.ListVpcGatewayEndpointsRequest(
            endpoint_id=endpoint_id,
            endpoint_name=endpoint_name,
            max_results=max(1, min(max_results, 100)),
            next_token=next_token,
        )
        resp = client.list_vpc_gateway_endpoints_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_ga_accelerators(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        accelerator_id: Optional[str] = None,
        state: Optional[str] = None,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举全球加速实例（ListAccelerators，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ga_client(account, rid)
        req = ga_models.ListAcceleratorsRequest(
            region_id=rid,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            accelerator_id=accelerator_id,
            state=state,
            resource_group_id=resource_group_id,
        )
        resp = client.list_accelerators_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_ga_listeners(
        account: str,
        accelerator_id: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举全球加速监听（ListListeners，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ga_client(account, rid)
        req = ga_models.ListListenersRequest(
            region_id=rid,
            accelerator_id=accelerator_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            protocol=protocol,
        )
        resp = client.list_listeners_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_ga_endpoint_groups(
        account: str,
        accelerator_id: str,
        region: Optional[str] = None,
        listener_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举全球加速终端节点组（ListEndpointGroups，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ga_client(account, rid)
        req = ga_models.ListEndpointGroupsRequest(
            region_id=rid,
            accelerator_id=accelerator_id,
            listener_id=listener_id,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
        )
        resp = client.list_endpoint_groups_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_waf_instance(
        account: str,
        region: Optional[str] = None,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 WAF 实例信息（DescribeInstance，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_waf_client(account, rid)
        req = waf_models.DescribeInstanceRequest(
            region_id=rid,
            resource_manager_resource_group_id=resource_group_id,
        )
        resp = client.describe_instance_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_waf_domains(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        domain: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 WAF 防护域名（DescribeDomains，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_waf_client(account, rid)
        req = waf_models.DescribeDomainsRequest(
            region_id=rid,
            instance_id=instance_id,
            domain=domain,
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            resource_manager_resource_group_id=resource_group_id,
        )
        resp = client.describe_domains_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_config_discovered_resources(
        account: str,
        region: Optional[str] = None,
        resource_types: Optional[List[str]] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        max_results: int = 100,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 Cloud Config 已发现资源（ListDiscoveredResources，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_config_client(account, rid)
        req = config_models.ListDiscoveredResourcesRequest(
            regions=[rid],
            resource_types=resource_types,
            resource_id=resource_id,
            resource_name=resource_name,
            max_results=max(1, min(max_results, 100)),
            next_token=next_token,
        )
        resp = client.list_discovered_resources_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_list_config_rules(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        config_rule_state: Optional[str] = None,
        risk_level: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 Cloud Config 规则（ListConfigRules，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_config_client(account, rid)
        req = config_models.ListConfigRulesRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            config_rule_state=config_rule_state,
            risk_level=risk_level,
            keyword=keyword,
        )
        resp = client.list_config_rules_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_get_config_rule_compliance(
        account: str,
        config_rule_id: str,
        compliance_type: Optional[str] = None,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 Cloud Config 规则的资源合规统计（GetResourceComplianceByConfigRule，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_config_client(account, rid)
        req = config_models.GetResourceComplianceByConfigRuleRequest(
            config_rule_id=config_rule_id,
            compliance_type=compliance_type,
        )
        resp = client.get_resource_compliance_by_config_rule_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_security_center_instances(
        account: str,
        region: Optional[str] = None,
        current_page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 Security Center 资产实例（DescribeCloudCenterInstances，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_sas_client(account, rid)
        req = sas_models.DescribeCloudCenterInstancesRequest(
            region_id=rid,
            current_page=max(1, current_page),
            page_size=max(1, min(page_size, 200)),
        )
        resp = client.describe_cloud_center_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_security_center_vul_list(
        account: str,
        region: Optional[str] = None,
        current_page: int = 1,
        page_size: int = 20,
        type: Optional[str] = None,
        dealed: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 Security Center 漏洞列表（DescribeVulList，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_sas_client(account, rid)
        req = sas_models.DescribeVulListRequest(
            current_page=max(1, current_page),
            page_size=max(1, min(page_size, 200)),
            type=type,
            dealed=dealed,
        )
        resp = client.describe_vul_list_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_antiddos_instances(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 Anti-DDoS 实例（DescribeInstances，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ddoscoo_client(account, rid)
        req = ddoscoo_models.DescribeInstancesRequest(
            page_number=max(1, page_number),
            page_size=max(1, min(page_size, 100)),
            status=status,
            ip=ip,
        )
        resp = client.describe_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_antiddos_domains(
        account: str,
        region: Optional[str] = None,
        instance_ids: Optional[List[str]] = None,
        resource_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列举 Anti-DDoS 域名防护对象（DescribeDomains，只读）。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")
        rid = _get_region(account, region)
        client = get_ddoscoo_client(account, rid)
        req = ddoscoo_models.DescribeDomainsRequest(
            instance_ids=instance_ids,
            resource_group_id=resource_group_id,
        )
        resp = client.describe_domains_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        result["region"] = rid
        return result

    @mcp.tool()
    def aliyun_describe_bastionhost_instances(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        instance_name: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举堡垒机实例（Bastionhost DescribeInstances，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            instance_id: 按实例 ID 过滤
            instance_name: 按实例名称过滤
            page_number: 页码
            page_size: 每页条数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")

        import requests
        
        rid = _get_region(account, region)
        creds = get_resolved_credentials(account)
        
        # 构建请求签名
        from aliyunsdkcore.auth.signer import Signer
        from aliyunsdkcore.auth.utils import percent_encode, quote
        from aliyunsdkcore.request import AcsRequest
        
        # 使用 AcsRequest 构建请求
        req = AcsRequest(
            host="yundun-bastionhost.aliyuncs.com",
            version="2020-12-10",
            action="DescribeInstances",
            uri_pattern="/",
            method="POST",
        )
        
        params = {
            "PageNumber": page_number,
            "PageSize": page_size,
        }
        if instance_id:
            params["InstanceId"] = instance_id
        if instance_name:
            params["InstanceName"] = instance_name
            
        for key, value in params.items():
            req.add_query_param(key, value)
        
        # 准备签名
        signer = Signer()
        credentials = {
            "access_key_id": creds.access_key_id,
            "access_key_secret": creds.access_key_secret,
        }
        if creds.security_token:
            credentials["security_token"] = creds.security_token
            req.add_query_param("SecurityToken", creds.security_token)
        
        # 发送请求
        try:
            url = f"https://{req.host}{req.uri_pattern}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "aliyun_mcp/1.0",
            }
            
            # 签名并发送
            signer.sign_request(credentials, req)
            
            body_params = {}
            body_params.update(params)
            body_params.update({
                "Action": req.action,
                "Version": req.version,
                "Signature": req.headers.get("Authorization", ""),
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "Timestamp": req.headers.get("Date", ""),
            })
            
            resp = requests.post(
                url,
                data=body_params,
                timeout=30,
            )
            
            if resp.status_code == 200:
                try:
                    result = resp.json()
                except:
                    result = {"raw_response": resp.text, "status_code": resp.status_code}
            else:
                result = {"error": f"HTTP {resp.status_code}", "message": resp.text}
            
            result["region"] = rid
            result["account"] = account
            return result
            
        except Exception as e:
            return {
                "region": rid,
                "account": account,
                "error": str(e),
                "note": "堡垒机查询需要依赖 requests 库。如果获取失败，请检查 IAM 权限是否包含 yundun-bastionhost 相关操作。",
            }

    @mcp.tool()
    def aliyun_describe_bastionhost_hosts(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举堡垒机资产（主机/Hosts，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            instance_id: 堡垒机实例 ID
            page_number: 页码
            page_size: 每页条数
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")

        import requests
        
        rid = _get_region(account, region)
        creds = get_resolved_credentials(account)
        
        try:
            from aliyunsdkcore.auth.signer import Signer
            from aliyunsdkcore.request import AcsRequest
            
            # 构建请求
            req = AcsRequest(
                host="yundun-bastionhost.aliyuncs.com",
                version="2020-12-10",
                action="ListHosts",
                uri_pattern="/",
                method="POST",
            )
            
            params = {
                "PageNumber": page_number,
                "PageSize": page_size,
            }
            if instance_id:
                params["InstanceId"] = instance_id
                
            for key, value in params.items():
                req.add_query_param(key, value)
            
            # 准备签名
            signer = Signer()
            credentials = {
                "access_key_id": creds.access_key_id,
                "access_key_secret": creds.access_key_secret,
            }
            if creds.security_token:
                credentials["security_token"] = creds.security_token
                req.add_query_param("SecurityToken", creds.security_token)
            
            # 发送请求
            url = f"https://{req.host}{req.uri_pattern}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "aliyun_mcp/1.0",
            }
            
            signer.sign_request(credentials, req)
            
            body_params = dict(params)
            body_params.update({
                "Action": req.action,
                "Version": req.version,
            })
            
            resp = requests.post(
                url,
                data=body_params,
                timeout=30,
            )
            
            if resp.status_code == 200:
                try:
                    result = resp.json()
                except:
                    result = {"raw_response": resp.text, "status_code": resp.status_code}
            else:
                result = {"error": f"HTTP {resp.status_code}", "message": resp.text}
            
            result["region"] = rid
            result["account"] = account
            return result
            
        except Exception as e:
            return {
                "region": rid,
                "account": account,
                "error": str(e),
                "note": "堡垒机资产查询需要依赖 requests 库与 aliyunsdkcore。如果获取失败，请检查 IAM 权限是否包含 yundun-bastionhost:ListHosts 操作。",
            }

    @mcp.tool()
    def aliyun_search_resource_center_resources(
        account: str,
        region: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_group_id: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: int = 50,
        next_token: Optional[str] = None,
        match_type: str = "Fuzzy",
        sort_order: str = "Desc",
    ) -> Dict[str, Any]:
        """
        通过 Resource Center 全局检索资源（SearchResources，只读）。

        参数:
            account: 账号标识（必填）
            region: 区域，默认账号默认区域
            resource_type: 资源类型，如 ACS::ECS::Instance
            resource_name: 资源名称关键字
            resource_id: 资源 ID
            resource_group_id: 资源组 ID
            keyword: 关键字检索表达式
            max_results: 每页条数，1-100
            next_token: 分页令牌
            match_type: 过滤匹配方式，支持 Fuzzy/Prefix/Exact
            sort_order: 排序方向，Asc 或 Desc
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")

        rid, client, rc_models = _get_resourcecenter_client(account, region)
        effective_max = min(max(max_results, 1), 100)
        effective_match_type = match_type if match_type in {"Fuzzy", "Prefix", "Exact"} else "Fuzzy"
        effective_sort_order = sort_order if sort_order in {"Asc", "Desc"} else "Desc"

        filters: List[Any] = []
        if resource_type:
            filters.append(rc_models.SearchResourcesRequestFilter(key="ResourceType", match_type="Exact", value=resource_type))
        if resource_name:
            filters.append(rc_models.SearchResourcesRequestFilter(key="ResourceName", match_type=effective_match_type, value=resource_name))
        if resource_id:
            filters.append(rc_models.SearchResourcesRequestFilter(key="ResourceId", match_type="Exact", value=resource_id))

        req = rc_models.SearchResourcesRequest(
            filter=filters or None,
            max_results=effective_max,
            next_token=next_token,
            resource_group_id=resource_group_id,
            search_expression=keyword,
            sort_criterion=rc_models.SearchResourcesRequestSortCriterion(key="CreateTime", order=effective_sort_order),
        )
        resp = client.search_resources_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        resources = _as_list(body.get("Resources") or body.get("resources"))
        return {
            "account": account,
            "region": rid,
            "query": {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "resource_id": resource_id,
                "resource_group_id": resource_group_id,
                "keyword": keyword,
                "match_type": effective_match_type,
                "max_results": effective_max,
                "next_token": next_token,
                "sort_order": effective_sort_order,
            },
            "count": len(resources),
            "next_token": body.get("NextToken") or body.get("next_token"),
            "resources": resources,
        }

    @mcp.tool()
    def aliyun_search_multi_account_resources(
        account: str,
        region: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        resource_id: Optional[str] = None,
        max_results: int = 50,
        next_token: Optional[str] = None,
        scope: str = "All",
        match_type: str = "Fuzzy",
        sort_order: str = "Desc",
    ) -> Dict[str, Any]:
        """
        跨账号检索资源（SearchMultiAccountResources，只读）。

        说明:
            需要已启用多账号资源中心并具备组织级权限；否则会返回权限或能力未开通错误。
        """
        if not validate_account(account):
            raise ValueError(f"无效的账号：{account}")

        rid, client, rc_models = _get_resourcecenter_client(account, region)
        effective_max = min(max(max_results, 1), 100)
        effective_scope = scope if scope in {"All", "ManagementAccount", "MemberAccount"} else "All"
        effective_match_type = match_type if match_type in {"Fuzzy", "Prefix", "Exact"} else "Fuzzy"
        effective_sort_order = sort_order if sort_order in {"Asc", "Desc"} else "Desc"

        filters: List[Any] = []
        if resource_type:
            filters.append(rc_models.SearchMultiAccountResourcesRequestFilter(key="ResourceType", match_type="Exact", value=resource_type))
        if resource_name:
            filters.append(rc_models.SearchMultiAccountResourcesRequestFilter(key="ResourceName", match_type=effective_match_type, value=resource_name))
        if resource_id:
            filters.append(rc_models.SearchMultiAccountResourcesRequestFilter(key="ResourceId", match_type="Exact", value=resource_id))

        req = rc_models.SearchMultiAccountResourcesRequest(
            filter=filters or None,
            max_results=effective_max,
            next_token=next_token,
            scope=effective_scope,
            sort_criterion=rc_models.SearchMultiAccountResourcesRequestSortCriterion(key="CreateTime", order=effective_sort_order),
        )
        resp = client.search_multi_account_resources_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        resources = _as_list(body.get("Resources") or body.get("resources"))
        return {
            "account": account,
            "region": rid,
            "query": {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "resource_id": resource_id,
                "scope": effective_scope,
                "match_type": effective_match_type,
                "max_results": effective_max,
                "next_token": next_token,
                "sort_order": effective_sort_order,
            },
            "count": len(resources),
            "next_token": body.get("NextToken") or body.get("next_token"),
            "resources": resources,
            "note": "若返回权限错误，请先在资源中心开通多账号检索能力并授予对应 RAM 权限。",
        }

    @mcp.tool()
    def aliyun_list_rocketmq_instances(
        account: str,
        region: Optional[str] = None,
        page_size: int = 20,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """
        列举 RocketMQ 实例（RocketMQ ListInstances，只读）。

        参数:
          account: 账号标识，从配置中取值
          region: 地域（可选），默认为实例配置地域或 cn-hangzhou
          page_size: 分页大小（最大 100，默认 20）
          page_number: 分页页码（从 1 开始）

        返回: {account, region, instances, total, page_info}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_rocketmq_client(account, rid)

        req = rmq_models.ListInstancesRequest(
            page_size=min(page_size, 100),
            page_number=max(page_number, 1),
        )
        resp = client.list_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        instances = _as_list(body.get("data") or body.get("Data") or [])
        
        return {
            "account": account,
            "region": rid,
            "page_info": {
                "page_size": page_size,
                "page_number": page_number,
            },
            "total": body.get("pageNumber"),
            "count": len(instances),
            "instances": instances,
        }

    @mcp.tool()
    def aliyun_list_rocketmq_topics(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        page_size: int = 20,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """
        列举 RocketMQ 主题（RocketMQ ListTopics，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          instance_id: 实例 ID（可选，若需要在特定实例中查询）
          page_size: 分页大小（默认 20）
          page_number: 分页页码

        返回: {account, region, topics, count}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_rocketmq_client(account, rid)

        req = rmq_models.ListTopicsRequest(
            page_size=min(page_size, 100),
            page_number=max(page_number, 1),
        )
        if instance_id:
            req.instance_id = instance_id
        
        resp = client.list_topics_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        topics = _as_list(body.get("data") or body.get("Data") or [])
        
        return {
            "account": account,
            "region": rid,
            "instance_id": instance_id,
            "count": len(topics),
            "topics": topics,
        }

    @mcp.tool()
    def aliyun_list_rocketmq_consumer_groups(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        page_size: int = 20,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """
        列举 RocketMQ 消费者组（RocketMQ ListConsumerGroups，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          instance_id: 实例 ID（可选）
          page_size: 分页大小（默认 20）
          page_number: 分页页码

        返回: {account, region, consumer_groups, count}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_rocketmq_client(account, rid)

        req = rmq_models.ListConsumerGroupsRequest(
            page_size=min(page_size, 100),
            page_number=max(page_number, 1),
        )
        if instance_id:
            req.instance_id = instance_id
        
        resp = client.list_consumer_groups_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        groups = _as_list(body.get("data") or body.get("Data") or [])
        
        return {
            "account": account,
            "region": rid,
            "instance_id": instance_id,
            "count": len(groups),
            "consumer_groups": groups,
        }

    @mcp.tool()
    def aliyun_describe_elasticsearch_instances(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        描述 Elasticsearch 实例（Elasticsearch DescribeInstance，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          instance_id: 实例 ID（需指定以查询单个实例详情）

        返回: {account, region, instance}
        """
        validate_account(account)
        rid = _get_region(account, region)
        
        if not instance_id:
            raise ValueError("instance_id 是必需参数，用以指定要查询的 Elasticsearch 实例")
        
        client = get_elasticsearch_client(account, rid)
        req = es_models.DescribeInstanceRequest(instance_id=instance_id)
        
        resp = client.describe_instance_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        instance = result.get("body", {}) if isinstance(result, dict) else {}
        
        return {
            "account": account,
            "region": rid,
            "instance_id": instance_id,
            "instance": instance,
        }

    @mcp.tool()
    def aliyun_describe_polardb_databases(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 PolarDB 数据库集群（PolarDB DescribeDBClusters，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          page_number: 分页页码（默认 1）
          page_size: 分页大小（默认 20）

        返回: {account, region, clusters, count, total}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_polardb_client(account, rid)

        req = polardb_models.DescribeDBClustersRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        
        resp = client.describe_dbclusters_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        clusters = _as_list(body.get("Items") or body.get("items") or [])
        
        return {
            "account": account,
            "region": rid,
            "page_info": {
                "page_number": page_number,
                "page_size": page_size,
            },
            "count": len(clusters),
            "total": body.get("TotalRecordCount") or body.get("totalRecordCount"),
            "clusters": clusters,
        }

    @mcp.tool()
    def aliyun_describe_alikafka_instances(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举 AliKafka 实例（AliKafka GetInstanceList，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          page_number: 分页页码（默认 1）
          page_size: 分页大小（默认 20）

        返回: {account, region, instances, count, total}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_alikafka_client(account, rid)

        req = kafka_models.GetInstanceListRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        
        resp = client.get_instance_list_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        instances = _as_list(body.get("InstanceList") or body.get("instanceList") or [])
        
        return {
            "account": account,
            "region": rid,
            "page_info": {
                "page_number": page_number,
                "page_size": page_size,
            },
            "count": len(instances),
            "total": body.get("Total") or body.get("total"),
            "instances": instances,
        }

    @mcp.tool()
    def aliyun_describe_dts_migration_jobs(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        列举数据传输服务 (DTS) 迁移任务（DTS DescribeMigrationJobs，只读）。

        参数:
          account: 账号标识
          region: 地域（可选）
          page_number: 分页页码（默认 1）
          page_size: 分页大小（默认 20）

        返回: {account, region, migration_jobs, count, total}
        """
        validate_account(account)
        rid = _get_region(account, region)
        client = get_dts_client(account, rid)

        req = dts_models.DescribeMigrationJobsRequest(
            page_num=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        
        resp = client.describe_migration_jobs_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        jobs = _as_list(body.get("MigrationJobs") or body.get("migrationJobs") or [])
        
        return {
            "account": account,
            "region": rid,
            "page_info": {
                "page_number": page_number,
                "page_size": page_size,
            },
            "count": len(jobs),
            "total": body.get("TotalRecordCount") or body.get("totalRecordCount"),
            "migration_jobs": jobs,
        }

    @mcp.tool()
    def aliyun_describe_dts_subscription_instances(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列举 DTS 订阅实例（DescribeSubscriptionInstances，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_dts_client(account, rid)

        req = dts_models.DescribeSubscriptionInstancesRequest(
            page_num=max(page_number, 1),
            page_size=min(page_size, 100),
            region_id=rid,
        )
        resp = client.describe_subscription_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        instances = _as_list(body.get("SubscriptionInstances") or body.get("subscriptionInstances"))
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_mse_applications(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 MSE 应用（GetApplicationList，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_mse_client(account, rid)

        req = mse_models.GetApplicationListRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
            region=rid,
        )
        if app_name:
            req.app_name = app_name
        resp = client.get_application_list_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        data = body.get("data") if isinstance(body, dict) else None
        apps = _as_list((data or {}).get("result") if isinstance(data, dict) else None)
        return {
            "account": account,
            "region": rid,
            "count": len(apps),
            "applications": apps,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_fc_services(
        account: str,
        region: Optional[str] = None,
        limit: int = 20,
        prefix: Optional[str] = None,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举函数计算服务（FC ListServices，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_fc_client(account, rid)

        req = fc_models.ListServicesRequest(limit=min(max(limit, 1), 100), next_token=next_token)
        if prefix:
            req.prefix = prefix
        resp = client.list_services_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        services = _as_list(body.get("services") or body.get("Services"))
        return {
            "account": account,
            "region": rid,
            "count": len(services),
            "services": services,
            "next_token": body.get("nextToken") or body.get("NextToken"),
        }

    @mcp.tool()
    def aliyun_list_fc_functions(
        account: str,
        service_name: str,
        region: Optional[str] = None,
        limit: int = 20,
        prefix: Optional[str] = None,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举函数计算函数（FC ListFunctions，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_fc_client(account, rid)

        req = fc_models.ListFunctionsRequest(limit=min(max(limit, 1), 100), next_token=next_token)
        if prefix:
            req.prefix = prefix
        resp = client.list_functions_with_options(service_name, req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        functions = _as_list(body.get("functions") or body.get("Functions"))
        return {
            "account": account,
            "region": rid,
            "service_name": service_name,
            "count": len(functions),
            "functions": functions,
            "next_token": body.get("nextToken") or body.get("NextToken"),
        }

    @mcp.tool()
    def aliyun_list_sae_applications(
        account: str,
        region: Optional[str] = None,
        namespace_id: Optional[str] = None,
        current_page: int = 1,
        page_size: int = 20,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 SAE 应用（ListApplications，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_sae_client(account, rid)

        req = sae_models.ListApplicationsRequest(
            current_page=max(current_page, 1),
            page_size=min(page_size, 100),
        )
        if namespace_id:
            req.namespace_id = namespace_id
        if app_name:
            req.app_name = app_name
        resp = client.list_applications_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        data = body.get("data") if isinstance(body, dict) else None
        apps = _as_list((data or {}).get("applications") if isinstance(data, dict) else None)
        return {
            "account": account,
            "region": rid,
            "count": len(apps),
            "applications": apps,
            "current_page": current_page,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_dataworks_projects(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列举 DataWorks 工作空间（ListProjects，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_dataworks_client(account, rid)

        req = dataworks_models.ListProjectsRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        resp = client.list_projects_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        projects = _as_list(body.get("Projects") or body.get("projects"))
        return {
            "account": account,
            "region": rid,
            "count": len(projects),
            "projects": projects,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_describe_analyticdb_instances(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        dbinstance_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 AnalyticDB PostgreSQL 实例（DescribeDBInstances，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_gpdb_client(account, rid)

        req = gpdb_models.DescribeDBInstancesRequest(
            region_id=rid,
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        if dbinstance_description:
            req.dbinstance_description = dbinstance_description
        resp = client.describe_dbinstances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        items = body.get("items") if isinstance(body, dict) else None
        instances = _as_list((items or {}).get("DBInstance") if isinstance(items, dict) else None)
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_emr_clusters(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 EMR 集群（ListClusters，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_emr_client(account, rid)

        req = emr_models.ListClustersRequest(
            region_id=rid,
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        if name:
            req.name = name
        resp = client.list_clusters_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        clusters = _as_list(body.get("ClusterList") or body.get("clusterList") or body.get("Clusters"))
        return {
            "account": account,
            "region": rid,
            "count": len(clusters),
            "clusters": clusters,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_nas_filesystems(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        file_system_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 NAS 文件系统（DescribeFileSystems，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_nas_client(account, rid)

        req = nas_models.DescribeFileSystemsRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        if file_system_type:
            req.file_system_type = file_system_type
        resp = client.describe_file_systems_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        filesystems = _as_list(body.get("FileSystems") or body.get("fileSystems"))
        return {
            "account": account,
            "region": rid,
            "count": len(filesystems),
            "filesystems": filesystems,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_pai_dlc_jobs(
        account: str,
        region: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        job_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 PAI DLC 任务（ListJobs，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_pai_dlc_client(account, rid)

        req = pai_models.ListJobsRequest(
            page_number=max(page_number, 1),
            page_size=min(page_size, 100),
        )
        if job_type:
            req.job_type = job_type
        resp = client.list_jobs_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        jobs = _as_list(body.get("jobs") or body.get("Jobs") or body.get("data"))
        return {
            "account": account,
            "region": rid,
            "count": len(jobs),
            "jobs": jobs,
            "page_number": page_number,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_hologres_instances(
        account: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 Hologres 实例（ListInstances，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_hologram_client(account, rid)

        req = hologram_models.ListInstancesRequest()
        resp = client.list_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        instances = _as_list(body.get("Instances") or body.get("instances"))
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
        }

    @mcp.tool()
    def aliyun_describe_asm_service_meshes(
        account: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 ASM 服务网格实例（DescribeServiceMeshes，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_servicemesh_client(account, rid)

        req = asm_models.DescribeServiceMeshesRequest()
        resp = client.describe_service_meshes_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        meshes = _as_list(body.get("ServiceMeshes") or body.get("serviceMeshes"))
        return {
            "account": account,
            "region": rid,
            "count": len(meshes),
            "service_meshes": meshes,
        }

    @mcp.tool()
    def aliyun_list_acr_namespaces(
        account: str,
        instance_id: str,
        region: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列举 ACR 命名空间（ListNamespace，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_cr_client(account, rid)

        req = acr_models.ListNamespaceRequest(
            instance_id=instance_id,
            page_no=max(page_no, 1),
            page_size=min(page_size, 100),
        )
        resp = client.list_namespace_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        namespaces = _as_list(body.get("namespaces") or body.get("Namespaces") or body.get("data"))
        return {
            "account": account,
            "region": rid,
            "instance_id": instance_id,
            "count": len(namespaces),
            "namespaces": namespaces,
            "page_no": page_no,
            "page_size": page_size,
        }

    @mcp.tool()
    def aliyun_list_arms_alerts(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        alert_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 ARMS 告警（ListAlerts，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_arms_client(account, rid)

        req = arms_models.ListAlertsRequest(
            region_id=rid,
            page=max(page, 1),
            size=min(size, 100),
        )
        if alert_name:
            req.alert_name = alert_name
        resp = client.list_alerts_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        alerts = _as_list(body.get("alerts") or body.get("Alerts") or body.get("data"))
        return {
            "account": account,
            "region": rid,
            "count": len(alerts),
            "alerts": alerts,
            "page": page,
            "size": size,
        }

    # ========================================================================
    # CLI-based tools for products without dedicated Python SDKs
    # ========================================================================

    def _call_aliyun_cli(product: str, api_name: str, params: Dict[str, Any], account: str) -> Dict[str, Any]:
        """Call Alibaba Cloud CLI and return parsed JSON response."""
        cmd = ["aliyun", product, api_name]
        
        # Add parameters
        for key, value in params.items():
            if value is not None:
                if isinstance(value, bool):
                    cmd.append(f"--{key}={str(value).lower()}")
                elif isinstance(value, (list, dict)):
                    cmd.append(f"--{key}={json.dumps(value)}")
                else:
                    cmd.append(f"--{key}={value}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"raw_output": result.stdout}
            else:
                return {"error": result.stderr, "returncode": result.returncode}
        except Exception as e:
            return {"error": str(e)}

    # TableStore Tools
    @mcp.tool()
    def aliyun_list_tablestore_tables(
        account: str,
        region: Optional[str] = None,
        instance_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud TableStore (OTS) tables（ListTable，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {}
        if instance_name:
            params["InstanceName"] = instance_name
        
        result = _call_aliyun_cli("tablestore", "ListTable", params, account)
        tables = _as_list(result.get("TableNames") or result.get("table_names") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(tables),
            "tables": tables,
            "instance_name": instance_name or "default",
        }

    @mcp.tool()
    def aliyun_describe_tablestore_instances(
        account: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud TableStore instances（DescribeInstances，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        result = _call_aliyun_cli("tablestore", "ListInstances", {}, account)
        instances = _as_list(result.get("InstanceInfos") or result.get("instances") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
        }

    # Lindorm (hitsdb) Tools
    @mcp.tool()
    def aliyun_list_lindorm_instances(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud Lindorm instances（GetLindormInstanceList，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "PageNumber": max(page, 1),
            "PageSize": min(size, 100),
        }
        
        result = _call_aliyun_cli("hitsdb", "GetLindormInstanceList", params, account)
        instances = _as_list(result.get("Instances") or result.get("instances") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_describe_lindorm_regions(
        account: str,
    ) -> Dict[str, Any]:
        """Describe Alibaba Cloud Lindorm available regions（DescribeRegions，只读）。"""
        validate_account(account)
        
        result = _call_aliyun_cli("hitsdb", "DescribeRegions", {}, account)
        regions = _as_list(result.get("Regions") or result.get("regions") or [])
        
        return {
            "account": account,
            "count": len(regions),
            "regions": regions,
        }

    @mcp.tool()
    def aliyun_get_lindorm_instance_summary(
        account: str,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get Alibaba Cloud Lindorm instance summary（GetInstanceSummary，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        if not instance_id:
            return {
                "account": account,
                "region": rid,
                "error": "instance_id is required",
            }
        
        params = {"InstanceId": instance_id}
        result = _call_aliyun_cli("hitsdb", "GetInstanceSummary", params, account)
        
        return {
            "account": account,
            "region": rid,
            "instance_id": instance_id,
            "summary": result,
        }

    # OOS Tools
    @mcp.tool()
    def aliyun_list_oos_templates(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud OOS templates（ListTemplates，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("oos", "ListTemplates", params, account)
        templates = _as_list(result.get("Templates") or result.get("templates") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(templates),
            "templates": templates,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_oos_executions(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud OOS executions（ListExecutions，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("oos", "ListExecutions", params, account)
        executions = _as_list(result.get("Executions") or result.get("executions") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(executions),
            "executions": executions,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_oos_parameters(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud OOS parameters（ListParameters，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("oos", "ListParameters", params, account)
        parameters = _as_list(result.get("Parameters") or result.get("parameters") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(parameters),
            "parameters": parameters,
            "page": page,
            "size": size,
        }

    # Cloud SSO Tools
    @mcp.tool()
    def aliyun_list_cloudsso_directories(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud CloudSSO directories（ListDirectories，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("cloudsso", "ListDirectories", params, account)
        directories = _as_list(result.get("Directories") or result.get("directories") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(directories),
            "directories": directories,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_cloudsso_users(
        account: str,
        region: Optional[str] = None,
        directory_id: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud CloudSSO users（ListUsers，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        if not directory_id:
            return {
                "account": account,
                "region": rid,
                "error": "directory_id is required",
            }
        
        params = {
            "DirectoryId": directory_id,
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("cloudsso", "ListUsers", params, account)
        users = _as_list(result.get("Users") or result.get("users") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(users),
            "users": users,
            "directory_id": directory_id,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_cloudsso_groups(
        account: str,
        region: Optional[str] = None,
        directory_id: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud CloudSSO groups（ListGroups，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        if not directory_id:
            return {
                "account": account,
                "region": rid,
                "error": "directory_id is required",
            }
        
        params = {
            "DirectoryId": directory_id,
            "MaxResults": min(size, 50),
            "PageNumber": max(page, 1),
        }
        
        result = _call_aliyun_cli("cloudsso", "ListGroups", params, account)
        groups = _as_list(result.get("Groups") or result.get("groups") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(groups),
            "groups": groups,
            "directory_id": directory_id,
            "page": page,
            "size": size,
        }

    # Express Connect Router Tools
    @mcp.tool()
    def aliyun_describe_express_connect_routers(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Alibaba Cloud Express Connect routers（DescribeExpressConnectRouter，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 100),
            "NextToken": "" if page == 1 else str((page - 1) * size),
        }
        
        result = _call_aliyun_cli("expressconnectrouter", "DescribeExpressConnectRouter", params, account)
        routers = _as_list(result.get("ExpressConnectRouters") or result.get("routers") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(routers),
            "routers": routers,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_describe_express_connect_router_regions(
        account: str,
    ) -> Dict[str, Any]:
        """List Express Connect Router available regions（DescribeExpressConnectRouterRegion，只读）。"""
        validate_account(account)
        
        result = _call_aliyun_cli("expressconnectrouter", "DescribeExpressConnectRouterRegion", {}, account)
        regions = _as_list(result.get("Regions") or result.get("regions") or [])
        
        return {
            "account": account,
            "count": len(regions),
            "regions": regions,
        }

    @mcp.tool()
    def aliyun_describe_express_connect_router_associations(
        account: str,
        region: Optional[str] = None,
        express_connect_router_id: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """List Express Connect Router associations（DescribeExpressConnectRouterAssociation，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        
        params = {
            "MaxResults": min(size, 100),
            "PageNumber": max(page, 1),
        }
        if express_connect_router_id:
            params["ExpressConnectRouterId"] = express_connect_router_id
        
        result = _call_aliyun_cli("expressconnectrouter", "DescribeExpressConnectRouterAssociation", params, account)
        associations = _as_list(result.get("Associations") or result.get("associations") or [])
        
        return {
            "account": account,
            "region": rid,
            "count": len(associations),
            "associations": associations,
            "express_connect_router_id": express_connect_router_id or "all",
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_maxcompute_quota_plans(
        account: str,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 MaxCompute 计算配额计划（ListComputeQuotaPlan，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_maxcompute_client(account, rid)

        req = maxcompute_models.ListComputeQuotaPlanRequest()
        resp = client.list_compute_quota_plan_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        plans = _as_list(body.get("data") or body.get("plans"))
        return {
            "account": account,
            "region": rid,
            "count": len(plans),
            "quota_plans": plans,
        }

    @mcp.tool()
    def aliyun_list_maxcompute_instances(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 MaxCompute 实例（ListInstances，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_maxcompute_client(account, rid)

        req = maxcompute_models.ListInstancesRequest(
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_instances_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        instances = _as_list(body.get("data") or body.get("instances"))
        return {
            "account": account,
            "region": rid,
            "count": len(instances),
            "instances": instances,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_eventbridge_event_buses(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 EventBridge 事件总线（ListEventBuses，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_eventbridge_client(account, rid)

        req = eventbridge_models.ListEventBusesRequest(
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_event_buses_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        buses = _as_list(body.get("data") or body.get("event_buses") or body.get("EventBuses"))
        return {
            "account": account,
            "region": rid,
            "count": len(buses),
            "event_buses": buses,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_eventbridge_connections(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 EventBridge 连接（ListConnections，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_eventbridge_client(account, rid)

        req = eventbridge_models.ListConnectionsRequest(
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_connections_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        connections = _as_list(body.get("data") or body.get("connections") or body.get("Connections"))
        return {
            "account": account,
            "region": rid,
            "count": len(connections),
            "connections": connections,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_eventbridge_rules(
        account: str,
        region: Optional[str] = None,
        event_bus_name: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 EventBridge 规则（ListRules，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_eventbridge_client(account, rid)

        req = eventbridge_models.ListRulesRequest(
            event_bus_name=event_bus_name or "default",
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_rules_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        rules = _as_list(body.get("data") or body.get("rules") or body.get("Rules"))
        return {
            "account": account,
            "region": rid,
            "count": len(rules),
            "rules": rules,
            "event_bus_name": event_bus_name or "default",
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_mns_queues(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 MNS 队列（ListQueue，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_mns_client(account, rid)

        req = mns_models.ListQueueRequest(
            page_base_zero=False,
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_queue_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        queues = _as_list(body.get("data") or body.get("queues") or body.get("Queues"))
        return {
            "account": account,
            "region": rid,
            "count": len(queues),
            "queues": queues,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_mns_topics(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """列举 MNS 主题（ListTopic，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_mns_client(account, rid)

        req = mns_models.ListTopicRequest(
            page_base_zero=False,
            page_number=max(page, 1),
            page_size=min(size, 100),
        )
        resp = client.list_topic_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        topics = _as_list(body.get("data") or body.get("topics") or body.get("Topics"))
        return {
            "account": account,
            "region": rid,
            "count": len(topics),
            "topics": topics,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_list_ros_stacks(
        account: str,
        region: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        stack_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举 ROS 栈（ListStacks，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_ros_client(account, rid)

        req = ros_models.ListStacksRequest(
            page_size=min(size, 50),
            page_number=max(page, 1),
            stack_name=stack_name,
        )
        resp = client.list_stacks_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        stacks = _as_list(body.get("data") or body.get("stacks") or body.get("Stacks"))
        return {
            "account": account,
            "region": rid,
            "count": len(stacks),
            "stacks": stacks,
            "page": page,
            "size": size,
        }

    @mcp.tool()
    def aliyun_describe_ros_resource_types(
        account: str,
        region: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """描述 ROS 资源类型（ListResourceTypes/DescribeResourceTypeDetail，只读）。"""
        validate_account(account)
        rid = _get_region(account, region)
        client = get_ros_client(account, rid)

        req = ros_models.ListResourceTypesRequest()
        resp = client.list_resource_types_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        types = _as_list(body.get("data") or body.get("resource_types") or body.get("ResourceTypes"))
        
        if resource_type:
            types = [t for t in types if isinstance(t, dict) and t.get("name") == resource_type]
        
        return {
            "account": account,
            "region": rid,
            "count": len(types),
            "resource_types": types,
            "filter": resource_type or "all",
        }

    @mcp.tool()
    def aliyun_describe_ros_regions(
        account: str,
    ) -> Dict[str, Any]:
        """描述 ROS 支持的地域（DescribeRegions，只读）。"""
        validate_account(account)
        rid = _get_region(account, None) or "cn-beijing"
        client = get_ros_client(account, rid)

        req = ros_models.DescribeRegionsRequest()
        resp = client.describe_regions_with_options(req, get_runtime_options())
        result = openapi_response_to_dict(resp)
        body = result.get("body", {}) if isinstance(result, dict) else {}
        regions = _as_list(body.get("data") or body.get("regions") or body.get("Regions"))
        return {
            "account": account,
            "count": len(regions),
            "regions": regions,
        }
