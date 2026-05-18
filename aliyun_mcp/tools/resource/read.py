"""
Read-only tools for common Alibaba Cloud products.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import oss2
from aliyun.log import LogClient
from alibabacloud_alb20200616 import models as alb_models
from alibabacloud_cs20151215 import models as cs_models
from alibabacloud_dds20151201 import models as dds_models
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_nlb20220430 import models as nlb_models
from alibabacloud_rds20140815 import models as rds_models
from alibabacloud_r_kvstore20150101 import models as kv_models
from alibabacloud_slb20140515 import models as slb_models
from alibabacloud_tag20180828 import models as tag_models
from alibabacloud_vpc20160428 import models as vpc_models

from aliyun_mcp.config.accounts import validate_account
from aliyun_mcp.core.client_factory import (
    get_alb_client,
    get_cs_client,
    get_dds_client,
    get_ecs_client,
    get_kvstore_client,
    get_nlb_client,
    get_rds_client,
    get_resolved_credentials,
    get_runtime_options,
    get_slb_client,
    get_tag_client,
    get_vpc_client,
)
from aliyun_mcp.utils.serialize import openapi_response_to_dict


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
