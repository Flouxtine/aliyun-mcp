"""
OpenAPI client factory: optional STS AssumeRole, fresh clients, timeouts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable, Dict, Optional, Tuple

from alibabacloud_actiontrail20200706.client import Client as ActiontrailClient
from alibabacloud_alb20200616.client import Client as AlbClient
from alibabacloud_bssopenapi20171214.client import Client as BssClient
from alibabacloud_cms20190101.client import Client as CmsClient
from alibabacloud_cs20151215.client import Client as CsClient
from alibabacloud_dds20151201.client import Client as DdsClient
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_nlb20220430.client import Client as NlbClient
from alibabacloud_ram20150501.client import Client as RamClient
from alibabacloud_rds20140815.client import Client as RdsClient
from alibabacloud_r_kvstore20150101.client import Client as KvstoreClient
from alibabacloud_slb20140515.client import Client as SlbClient
from alibabacloud_sts20150401.client import Client as StsClient
from alibabacloud_sts20150401 import models as sts_models
from alibabacloud_tag20180828.client import Client as TagClient
from alibabacloud_tea_openapi import utils_models as open_api_util_models
from alibabacloud_vpc20160428.client import Client as VpcClient
from alibabacloud_kms20160120.client import Client as KmsClient
from alibabacloud_alidns20150109.client import Client as AlidnsClient
from alibabacloud_cbn20170912.client import Client as CbnClient
from alibabacloud_cdn20180510.client import Client as CdnClient
from alibabacloud_config20200907.client import Client as ConfigClient
from darabonba.runtime import RuntimeOptions
from alibabacloud_dcdn20180115.client import Client as DcdnClient
from alibabacloud_ddoscoo20200101.client import Client as DdoscooClient
from alibabacloud_ga20191120.client import Client as GaClient
from alibabacloud_sas20181203.client import Client as SasClient
from alibabacloud_waf_openapi20211001.client import Client as WafClient
from alibabacloud_polardb20170801.client import Client as PolardbClient
from alibabacloud_elasticsearch20170613.client import Client as ElasticsearchClient
from alibabacloud_rocketmq20220801.client import Client as RocketmqClient
from alibabacloud_alikafka20190916.client import Client as AlikafkaClient
from alibabacloud_dts20200101.client import Client as DtsClient
from alibabacloud_mse20190531.client import Client as MseClient
from alibabacloud_fc_open20210406.client import Client as FcClient
from alibabacloud_sae20190506.client import Client as SaeClient
from alibabacloud_dataworks_public20200518.client import Client as DataworksClient
from alibabacloud_gpdb20160503.client import Client as GpdbClient
from alibabacloud_emr20160408.client import Client as EmrClient
from alibabacloud_pai_dlc20201203.client import Client as PaiDlcClient
from alibabacloud_nas20170626.client import Client as NasClient
from alibabacloud_hologram20220601.client import Client as HologramClient
from alibabacloud_cr20181201.client import Client as CrClient
from alibabacloud_servicemesh20200111.client import Client as ServicemeshClient
from alibabacloud_arms20190808.client import Client as ArmsClient
from alibabacloud_maxcompute20220104.client import Client as MaxcomputeClient
from alibabacloud_eventbridge20200401.client import Client as EventbridgeClient
from alibabacloud_mns_open20220119.client import Client as MnsClient
from alibabacloud_ros20190910.client import Client as RosClient

from aliyun_mcp.config.accounts import AccountConfig, get_account_config

_runtime = RuntimeOptions(read_timeout=120000, connect_timeout=10000)
_cache_lock = RLock()
_creds_cache: Dict[str, Tuple[ResolvedCreds, Optional[datetime]]] = {}
_client_cache: Dict[Tuple[str, str, str, str], Any] = {}
_STS_REFRESH_WINDOW = timedelta(minutes=5)


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


def _cache_expired(expiration: Optional[datetime]) -> bool:
    if expiration is None:
        return False
    now = datetime.now(timezone.utc) if expiration.tzinfo else datetime.utcnow()
    return now + _STS_REFRESH_WINDOW >= expiration


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

    with _cache_lock:
        cached = _creds_cache.get(account.name)
        if cached and not _cache_expired(cached[1]):
            return cached[0]

    creds, expiration = _assume_role(account)
    with _cache_lock:
        _creds_cache[account.name] = (creds, expiration)
        for key in list(_client_cache):
            if key[1] == account.name:
                _client_cache.pop(key, None)
    return creds


def get_runtime_options() -> RuntimeOptions:
    return _runtime


def clear_client_cache() -> None:
    """Called after ``reload_accounts()``; extend if module-level client caches are added."""
    with _cache_lock:
        _creds_cache.clear()
        _client_cache.clear()


def get_resolved_credentials(account_key: str) -> ResolvedCreds:
    return _resolve_runtime_credentials(get_account_config(account_key))


def _build_client(
    service: str,
    account_key: str,
    region: Optional[str],
    factory: Callable[[open_api_util_models.Config], Any],
):
    cfg = get_account_config(account_key)
    region_id = region or cfg.default_region
    creds = _resolve_runtime_credentials(cfg)
    cache_key = (service, cfg.name, region_id, creds.access_key_id)
    with _cache_lock:
        cached = _client_cache.get(cache_key)
        if cached is not None:
            return cached

    client = factory(_openapi_config(creds, region_id))
    with _cache_lock:
        _client_cache[cache_key] = client
    return client


def get_ecs_client(account_key: str, region: Optional[str] = None) -> EcsClient:
    return _build_client("ecs", account_key, region, lambda c: EcsClient(c))


def get_vpc_client(account_key: str, region: Optional[str] = None) -> VpcClient:
    return _build_client("vpc", account_key, region, lambda c: VpcClient(c))


def get_tag_client(account_key: str, region: Optional[str] = None) -> TagClient:
    return _build_client("tag", account_key, region, lambda c: TagClient(c))


def get_bss_client(account_key: str, region: Optional[str] = None) -> BssClient:
    return _build_client("bss", account_key, region, lambda c: BssClient(c))


def get_cms_client(account_key: str, region: Optional[str] = None) -> CmsClient:
    return _build_client("cms", account_key, region, lambda c: CmsClient(c))


def get_actiontrail_client(account_key: str, region: Optional[str] = None) -> ActiontrailClient:
    return _build_client("actiontrail", account_key, region, lambda c: ActiontrailClient(c))


def get_alb_client(account_key: str, region: Optional[str] = None) -> AlbClient:
    return _build_client("alb", account_key, region, lambda c: AlbClient(c))


def get_nlb_client(account_key: str, region: Optional[str] = None) -> NlbClient:
    return _build_client("nlb", account_key, region, lambda c: NlbClient(c))


def get_kvstore_client(account_key: str, region: Optional[str] = None) -> KvstoreClient:
    return _build_client("kvstore", account_key, region, lambda c: KvstoreClient(c))


def get_dds_client(account_key: str, region: Optional[str] = None) -> DdsClient:
    return _build_client("dds", account_key, region, lambda c: DdsClient(c))


def get_cs_client(account_key: str, region: Optional[str] = None) -> CsClient:
    return _build_client("cs", account_key, region, lambda c: CsClient(c))


def get_rds_client(account_key: str, region: Optional[str] = None) -> RdsClient:
    return _build_client("rds", account_key, region, lambda c: RdsClient(c))


def get_slb_client(account_key: str, region: Optional[str] = None) -> SlbClient:
    return _build_client("slb", account_key, region, lambda c: SlbClient(c))


def get_ram_client(account_key: str, region: Optional[str] = None) -> RamClient:
    return _build_client("ram", account_key, region, lambda c: RamClient(c))


def get_kms_client(account_key: str, region: Optional[str] = None) -> KmsClient:
    return _build_client("kms", account_key, region, lambda c: KmsClient(c))


def get_alidns_client(account_key: str, region: Optional[str] = None) -> AlidnsClient:
    return _build_client("alidns", account_key, region, lambda c: AlidnsClient(c))


def get_cdn_client(account_key: str, region: Optional[str] = None) -> CdnClient:
    return _build_client("cdn", account_key, region, lambda c: CdnClient(c))


def get_dcdn_client(account_key: str, region: Optional[str] = None) -> DcdnClient:
    return _build_client("dcdn", account_key, region, lambda c: DcdnClient(c))


def get_cbn_client(account_key: str, region: Optional[str] = None) -> CbnClient:
    return _build_client("cbn", account_key, region, lambda c: CbnClient(c))


def get_ga_client(account_key: str, region: Optional[str] = None) -> GaClient:
    return _build_client("ga", account_key, region, lambda c: GaClient(c))


def get_waf_client(account_key: str, region: Optional[str] = None) -> WafClient:
    return _build_client("waf", account_key, region, lambda c: WafClient(c))


def get_config_client(account_key: str, region: Optional[str] = None) -> ConfigClient:
    return _build_client("config", account_key, region, lambda c: ConfigClient(c))


def get_sas_client(account_key: str, region: Optional[str] = None) -> SasClient:
    return _build_client("sas", account_key, region, lambda c: SasClient(c))


def get_ddoscoo_client(account_key: str, region: Optional[str] = None) -> DdoscooClient:
    return _build_client("ddoscoo", account_key, region, lambda c: DdoscooClient(c))


def get_polardb_client(account_key: str, region: Optional[str] = None) -> PolardbClient:
    return _build_client("polardb", account_key, region, lambda c: PolardbClient(c))


def get_elasticsearch_client(account_key: str, region: Optional[str] = None) -> ElasticsearchClient:
    return _build_client("elasticsearch", account_key, region, lambda c: ElasticsearchClient(c))


def get_rocketmq_client(account_key: str, region: Optional[str] = None) -> RocketmqClient:
    return _build_client("rocketmq", account_key, region, lambda c: RocketmqClient(c))


def get_alikafka_client(account_key: str, region: Optional[str] = None) -> AlikafkaClient:
    return _build_client("alikafka", account_key, region, lambda c: AlikafkaClient(c))


def get_dts_client(account_key: str, region: Optional[str] = None) -> DtsClient:
    return _build_client("dts", account_key, region, lambda c: DtsClient(c))


def get_mse_client(account_key: str, region: Optional[str] = None) -> MseClient:
    return _build_client("mse", account_key, region, lambda c: MseClient(c))


def get_fc_client(account_key: str, region: Optional[str] = None) -> FcClient:
    return _build_client("fc", account_key, region, lambda c: FcClient(c))


def get_sae_client(account_key: str, region: Optional[str] = None) -> SaeClient:
    return _build_client("sae", account_key, region, lambda c: SaeClient(c))


def get_dataworks_client(account_key: str, region: Optional[str] = None) -> DataworksClient:
    return _build_client("dataworks", account_key, region, lambda c: DataworksClient(c))


def get_gpdb_client(account_key: str, region: Optional[str] = None) -> GpdbClient:
    return _build_client("gpdb", account_key, region, lambda c: GpdbClient(c))


def get_emr_client(account_key: str, region: Optional[str] = None) -> EmrClient:
    return _build_client("emr", account_key, region, lambda c: EmrClient(c))


def get_pai_dlc_client(account_key: str, region: Optional[str] = None) -> PaiDlcClient:
    return _build_client("pai_dlc", account_key, region, lambda c: PaiDlcClient(c))


def get_nas_client(account_key: str, region: Optional[str] = None) -> NasClient:
    return _build_client("nas", account_key, region, lambda c: NasClient(c))


def get_hologram_client(account_key: str, region: Optional[str] = None) -> HologramClient:
    return _build_client("hologram", account_key, region, lambda c: HologramClient(c))


def get_cr_client(account_key: str, region: Optional[str] = None) -> CrClient:
    return _build_client("cr", account_key, region, lambda c: CrClient(c))


def get_servicemesh_client(account_key: str, region: Optional[str] = None) -> ServicemeshClient:
    return _build_client("servicemesh", account_key, region, lambda c: ServicemeshClient(c))


def get_arms_client(account_key: str, region: Optional[str] = None) -> ArmsClient:
    return _build_client("arms", account_key, region, lambda c: ArmsClient(c))


def get_maxcompute_client(account_key: str, region: Optional[str] = None) -> MaxcomputeClient:
    return _build_client("maxcompute", account_key, region, lambda c: MaxcomputeClient(c))


def get_eventbridge_client(account_key: str, region: Optional[str] = None) -> EventbridgeClient:
    return _build_client("eventbridge", account_key, region, lambda c: EventbridgeClient(c))


def get_mns_client(account_key: str, region: Optional[str] = None) -> MnsClient:
    return _build_client("mns", account_key, region, lambda c: MnsClient(c))


def get_ros_client(account_key: str, region: Optional[str] = None) -> RosClient:
    return _build_client("ros", account_key, region, lambda c: RosClient(c))
