"""
OpenAPI client factory: optional STS AssumeRole, fresh clients, timeouts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional, Tuple

from alibabacloud_actiontrail20200706.client import Client as ActiontrailClient
from alibabacloud_alb20200616.client import Client as AlbClient
from alibabacloud_bssopenapi20171214.client import Client as BssClient
from alibabacloud_cms20190101.client import Client as CmsClient
from alibabacloud_cs20151215.client import Client as CsClient
from alibabacloud_dds20151201.client import Client as DdsClient
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_nlb20220430.client import Client as NlbClient
from alibabacloud_rds20140815.client import Client as RdsClient
from alibabacloud_r_kvstore20150101.client import Client as KvstoreClient
from alibabacloud_slb20140515.client import Client as SlbClient
from alibabacloud_sts20150401.client import Client as StsClient
from alibabacloud_sts20150401 import models as sts_models
from alibabacloud_tag20180828.client import Client as TagClient
from alibabacloud_tea_openapi import utils_models as open_api_util_models
from alibabacloud_vpc20160428.client import Client as VpcClient
from darabonba.runtime import RuntimeOptions

from aliyun_mcp.config.accounts import AccountConfig, get_account_config

_runtime = RuntimeOptions(read_timeout=120000, connect_timeout=10000)


@dataclass(frozen=True)
class ResolvedCreds:
    access_key_id: str
    access_key_secret: str
    security_token: Optional[str]


def _openapi_config(creds: ResolvedCreds, region_id: str) -> open_api_util_models.Config:
    cfg = open_api_util_models.Config(
        access_key_id=creds.access_key_id,
        access_key_secret=creds.access_key_secret,
        security_token=creds.security_token,
        region_id=region_id,
        read_timeout=120000,
        connect_timeout=10000,
    )
    return cfg


def _parse_expiration(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _assume_role(account: AccountConfig) -> Tuple[ResolvedCreds, Optional[datetime]]:
    base = open_api_util_models.Config(
        access_key_id=account.access_key_id,
        access_key_secret=account.access_key_secret,
        region_id=account.default_region,
    )
    sts = StsClient(base)
    req = sts_models.AssumeRoleRequest(
        role_arn=account.role_arn,
        role_session_name=account.role_session_name or "aliyun-mcp",
    )
    resp = sts.assume_role_with_options(req, _runtime)
    body = resp.body
    if body is None or body.credentials is None:
        raise RuntimeError("AssumeRole 返回为空，请检查 ROLE_ARN 与 RAM 信任策略")
    creds_obj = body.credentials
    expiration = _parse_expiration(getattr(creds_obj, "expiration", None))
    resolved = ResolvedCreds(
        access_key_id=creds_obj.access_key_id,
        access_key_secret=creds_obj.access_key_secret,
        security_token=creds_obj.security_token,
    )
    return resolved, expiration


def _resolve_runtime_credentials(account: AccountConfig) -> ResolvedCreds:
    if not account.role_arn:
        return ResolvedCreds(
            access_key_id=account.access_key_id,
            access_key_secret=account.access_key_secret,
            security_token=None,
        )

    creds, _expiration = _assume_role(account)
    return creds


def get_runtime_options() -> RuntimeOptions:
    return _runtime


def clear_client_cache() -> None:
    """Called after ``reload_accounts()``; extend if module-level client caches are added."""
    return


def get_resolved_credentials(account_key: str) -> ResolvedCreds:
    return _resolve_runtime_credentials(get_account_config(account_key))


def _build_client(
    account_key: str,
    region: Optional[str],
    factory: Callable[[open_api_util_models.Config], Any],
):
    cfg = get_account_config(account_key)
    region_id = region or cfg.default_region
    creds = _resolve_runtime_credentials(cfg)
    return factory(_openapi_config(creds, region_id))


def get_ecs_client(account_key: str, region: Optional[str] = None) -> EcsClient:
    return _build_client(account_key, region, lambda c: EcsClient(c))


def get_vpc_client(account_key: str, region: Optional[str] = None) -> VpcClient:
    return _build_client(account_key, region, lambda c: VpcClient(c))


def get_tag_client(account_key: str, region: Optional[str] = None) -> TagClient:
    return _build_client(account_key, region, lambda c: TagClient(c))


def get_bss_client(account_key: str, region: Optional[str] = None) -> BssClient:
    return _build_client(account_key, region, lambda c: BssClient(c))


def get_cms_client(account_key: str, region: Optional[str] = None) -> CmsClient:
    return _build_client(account_key, region, lambda c: CmsClient(c))


def get_actiontrail_client(account_key: str, region: Optional[str] = None) -> ActiontrailClient:
    return _build_client(account_key, region, lambda c: ActiontrailClient(c))


def get_alb_client(account_key: str, region: Optional[str] = None) -> AlbClient:
    return _build_client(account_key, region, lambda c: AlbClient(c))


def get_nlb_client(account_key: str, region: Optional[str] = None) -> NlbClient:
    return _build_client(account_key, region, lambda c: NlbClient(c))


def get_kvstore_client(account_key: str, region: Optional[str] = None) -> KvstoreClient:
    return _build_client(account_key, region, lambda c: KvstoreClient(c))


def get_dds_client(account_key: str, region: Optional[str] = None) -> DdsClient:
    return _build_client(account_key, region, lambda c: DdsClient(c))


def get_cs_client(account_key: str, region: Optional[str] = None) -> CsClient:
    return _build_client(account_key, region, lambda c: CsClient(c))


def get_rds_client(account_key: str, region: Optional[str] = None) -> RdsClient:
    return _build_client(account_key, region, lambda c: RdsClient(c))


def get_slb_client(account_key: str, region: Optional[str] = None) -> SlbClient:
    return _build_client(account_key, region, lambda c: SlbClient(c))
