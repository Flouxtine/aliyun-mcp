"""
Alibaba Cloud account configuration (multi-account via environment variables).

AccessKey resolution order:
1) direct env vars (highest priority)
2) explicitly configured CLI profile via ALIYUN_ACCOUNT_{KEY}_CLI_PROFILE
3) automatic local CLI profile fallback (account key -> default)
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()


class AccountConfig(BaseModel):
    """RAM access configuration for one logical account."""

    access_key_id: str = Field(..., description="AccessKey ID")
    access_key_secret: str = Field(..., description="AccessKey Secret")
    default_region: str = Field(..., description="Default region id, e.g. cn-hangzhou")
    name: str = Field(..., description="Account key (lowercase identifier)")
    account_name: str = Field(..., description="Display name")
    description: str = Field(default="", description="Optional description from env (superseded by code resources)")
    role_arn: Optional[str] = Field(default=None, description="Optional RAM role ARN for STS AssumeRole")
    role_session_name: str = Field(default="aliyun-mcp", description="STS session name when using role_arn")


ACCOUNT_ENV_PATTERN = re.compile(
    r"^ALIYUN_ACCOUNT_([A-Z0-9_]+)_("
    r"ACCESS_KEY_ID|ACCESS_KEY_SECRET|DEFAULT_REGION|ACCOUNT_NAME|DESCRIPTION|ROLE_ARN|ROLE_SESSION_NAME|CLI_PROFILE"
    r")$"
)

RELOAD_ENV_PREFIXES = ("ALIYUN_ACCOUNT_", "ALIYUN_RD_")

_accounts_cache: Optional[Dict[str, AccountConfig]] = None
_last_dotenv_path: Optional[str] = None


def _env_bool(name: str, default: bool = False) -> bool:
    value = (os.environ.get(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _safe_validation_summary(err: ValidationError) -> str:
    """Return field-level validation summary without echoing input values (secrets)."""
    fields: List[str] = []
    for item in err.errors():
        loc = item.get("loc", ())
        if loc:
            fields.append(".".join(str(x) for x in loc))

    unique_fields = sorted(set(fields))
    if unique_fields:
        return f"字段异常: {', '.join(unique_fields)}"
    return "字段异常"


def _cli_config_path() -> str:
    return os.environ.get("ALIYUN_CLI_CONFIG_PATH") or os.path.expanduser("~/.aliyun/config.json")


def _resolve_dotenv_path() -> str:
    return os.environ.get("ALIYUN_DOTENV_PATH") or find_dotenv(usecwd=True) or ""


def _load_cli_profile_credentials(profile_name: str) -> Dict[str, str]:
    """Load AK + region from Alibaba Cloud CLI config (AK mode only)."""
    path = _cli_config_path()
    if not os.path.isfile(path):
        raise ValueError(f"阿里云 CLI 配置文件不存在: {path}（可设置 ALIYUN_CLI_CONFIG_PATH）")

    with open(path, encoding="utf-8") as f:
        cfg: Dict[str, Any] = json.load(f)

    for prof in cfg.get("profiles", []):
        if prof.get("name") != profile_name:
            continue
        if prof.get("mode") != "AK":
            raise ValueError(
                f"CLI profile '{profile_name}' 的 mode 为 {prof.get('mode')!r}，"
                f"当前 MCP 仅支持从 AK 模式的 profile 读取密钥"
            )
        ak = prof.get("access_key_id")
        sk = prof.get("access_key_secret")
        if not ak or not sk:
            raise ValueError(f"CLI profile '{profile_name}' 缺少 access_key_id / access_key_secret")
        region = prof.get("region_id") or "cn-hangzhou"
        return {
            "access_key_id": ak,
            "access_key_secret": sk,
            "default_region": region,
        }

    raise ValueError(f"在 {_cli_config_path()} 中未找到名为 '{profile_name}' 的 profile")


def _merge_cli_profile(account_key: str, account_data: Dict[str, str]) -> None:
    """Fill missing AK/region from CLI config while keeping env vars as highest priority."""
    explicit_profile_name = (account_data.get("cli_profile") or "").strip()

    if explicit_profile_name:
        # Explicit profile must be valid, otherwise fail fast.
        creds = _load_cli_profile_credentials(explicit_profile_name)
        account_data.setdefault("access_key_id", creds["access_key_id"])
        account_data.setdefault("access_key_secret", creds["access_key_secret"])
        account_data.setdefault("default_region", creds["default_region"])
        return

    # Auto fallback: try profile named as account key, then default.
    for profile_name in [account_key, "default"]:
        try:
            creds = _load_cli_profile_credentials(profile_name)
            account_data.setdefault("access_key_id", creds["access_key_id"])
            account_data.setdefault("access_key_secret", creds["access_key_secret"])
            account_data.setdefault("default_region", creds["default_region"])
            return
        except ValueError:
            continue


def _list_rd_member_accounts(manager: AccountConfig) -> List[Dict[str, str]]:
    """List member accounts from Resource Directory using manager account AK/SK."""
    try:
        from alibabacloud_resourcemanager20200331.client import Client as ResourceManagerClient
        from alibabacloud_resourcemanager20200331 import models as rm_models
        from alibabacloud_tea_openapi import utils_models as open_api_util_models
        from darabonba.runtime import RuntimeOptions
    except ImportError as e:
        raise ValueError(
            "启用 RD 自动发现需要依赖 alibabacloud-resourcemanager20200331，请先安装项目依赖。"
        ) from e

    cfg = open_api_util_models.Config(
        access_key_id=manager.access_key_id,
        access_key_secret=manager.access_key_secret,
        region_id=manager.default_region,
        read_timeout=120000,
        connect_timeout=10000,
    )
    client = ResourceManagerClient(cfg)
    runtime = RuntimeOptions(read_timeout=120000, connect_timeout=10000)

    items: List[Dict[str, str]] = []
    next_token: Optional[str] = None
    while True:
        req = rm_models.ListAccountsRequest(max_results=50, next_token=next_token)
        resp = client.list_accounts_with_options(req, runtime)
        body = getattr(resp, "body", None)

        accounts_obj = getattr(body, "accounts", None)
        account_list = getattr(accounts_obj, "account", None) or []

        for entry in account_list:
            account_id = getattr(entry, "account_id", None) or getattr(entry, "id", None)
            if not account_id:
                continue

            display_name = getattr(entry, "display_name", None) or getattr(entry, "account_name", None) or account_id
            status = getattr(entry, "status", None) or "Unknown"
            items.append(
                {
                    "account_id": str(account_id),
                    "display_name": str(display_name),
                    "status": str(status),
                }
            )

        next_token = getattr(body, "next_token", None)
        if not next_token:
            break

    return items


def _append_rd_discovered_accounts(accounts: Dict[str, AccountConfig]) -> None:
    """Append auto-discovered RD member accounts as role-based logical accounts."""
    if not _env_bool("ALIYUN_RD_AUTO_DISCOVERY", default=False):
        return

    manager_key = (os.environ.get("ALIYUN_RD_MANAGER_ACCOUNT_KEY") or "").strip().lower()
    if not manager_key:
        raise ValueError("启用 RD 自动发现时必须设置 ALIYUN_RD_MANAGER_ACCOUNT_KEY")
    if manager_key not in accounts:
        raise ValueError(f"ALIYUN_RD_MANAGER_ACCOUNT_KEY={manager_key} 未在已配置账号中找到")

    manager = accounts[manager_key]
    role_name = (os.environ.get("ALIYUN_RD_ROLE_NAME") or "ReadOnlyForMcp").strip()
    role_session_name = (os.environ.get("ALIYUN_RD_ROLE_SESSION_NAME") or "aliyun-mcp").strip()
    key_prefix = (os.environ.get("ALIYUN_RD_ACCOUNT_KEY_PREFIX") or "rd").strip().lower().replace("-", "_")
    default_region = (os.environ.get("ALIYUN_RD_DEFAULT_REGION") or manager.default_region).strip()
    include_suspended = _env_bool("ALIYUN_RD_INCLUDE_SUSPENDED", default=False)

    if not role_name:
        raise ValueError("ALIYUN_RD_ROLE_NAME 不能为空")

    members = _list_rd_member_accounts(manager)
    for member in members:
        account_id = member["account_id"]
        status = member.get("status", "Unknown")

        if (status or "").lower() == "suspended" and not include_suspended:
            continue
        if account_id == manager.name:
            continue

        account_key = f"{key_prefix}_{account_id}"
        if account_key in accounts:
            continue

        role_arn = f"acs:ram::{account_id}:role/{role_name}"
        accounts[account_key] = AccountConfig(
            access_key_id=manager.access_key_id,
            access_key_secret=manager.access_key_secret,
            default_region=default_region,
            name=account_key,
            account_name=member.get("display_name", account_id),
            description=f"RD auto-discovered account ({status})",
            role_arn=role_arn,
            role_session_name=role_session_name or "aliyun-mcp",
        )


def _load_accounts() -> Dict[str, AccountConfig]:
    accounts_raw: Dict[str, Dict[str, str]] = {}

    for key, value in os.environ.items():
        match = ACCOUNT_ENV_PATTERN.match(key)
        if not match:
            continue

        account_key = match.group(1).lower()
        field_name = match.group(2).lower()

        if account_key not in accounts_raw:
            accounts_raw[account_key] = {"name": account_key}

        accounts_raw[account_key][field_name] = value

    accounts: Dict[str, AccountConfig] = {}
    for account_key, account_data in accounts_raw.items():
        try:
            if "account_name" not in account_data:
                account_data["account_name"] = account_key
            if "description" not in account_data:
                account_data["description"] = ""
            if account_data.get("role_arn") == "":
                account_data["role_arn"] = None

            _merge_cli_profile(account_key, account_data)
            account_data.pop("cli_profile", None)

            account = AccountConfig(**account_data)
            accounts[account_key] = account
        except ValidationError as e:
            raise ValueError(f"账号 '{account_key}' 配置无效（{_safe_validation_summary(e)}）") from e

    _append_rd_discovered_accounts(accounts)

    if not accounts:
        raise ValueError("未配置任何阿里云账号，请设置 ALIYUN_ACCOUNT_* 环境变量。")

    return accounts


def get_account_config(account_name: str) -> AccountConfig:
    global _accounts_cache

    if _accounts_cache is None:
        _accounts_cache = _load_accounts()

    account_key_lower = account_name.lower()
    if account_key_lower not in _accounts_cache:
        raise ValueError(
            f"账号 '{account_name}' 不存在。可用账号：{', '.join(_accounts_cache.keys())}"
        )

    return _accounts_cache[account_key_lower]


def list_accounts() -> List[str]:
    global _accounts_cache

    if _accounts_cache is None:
        _accounts_cache = _load_accounts()

    return list(_accounts_cache.keys())


def validate_account(account_name: str) -> bool:
    global _accounts_cache

    if _accounts_cache is None:
        _accounts_cache = _load_accounts()

    return account_name.lower() in _accounts_cache


def reload_accounts() -> None:
    global _accounts_cache, _last_dotenv_path

    # Drop stale ALIYUN_* values managed by .env before reloading.
    for key in list(os.environ.keys()):
        if key.startswith(RELOAD_ENV_PREFIXES):
            os.environ.pop(key, None)

    dotenv_path = _resolve_dotenv_path()
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=True)
        _last_dotenv_path = dotenv_path

    _accounts_cache = None
    from aliyun_mcp.core.client_factory import clear_client_cache

    clear_client_cache()
    _load_accounts()


def get_config_diagnostics() -> Dict[str, Any]:
    """Return safe configuration diagnostics without exposing credentials."""
    global _accounts_cache

    dotenv_path = _last_dotenv_path or _resolve_dotenv_path()
    dotenv_exists = bool(dotenv_path and os.path.isfile(dotenv_path))

    env_account_keys = sorted(
        {
            match.group(1).lower()
            for key in os.environ.keys()
            if (match := ACCOUNT_ENV_PATTERN.match(key))
        }
    )

    try:
        if _accounts_cache is None:
            _accounts_cache = _load_accounts()
        loaded_account_keys = sorted(_accounts_cache.keys())
        load_error = None
    except Exception as e:
        loaded_account_keys = []
        load_error = str(e)

    return {
        "dotenv_path": dotenv_path,
        "dotenv_exists": dotenv_exists,
        "env_account_keys": env_account_keys,
        "loaded_account_keys": loaded_account_keys,
        "rd_auto_discovery": _env_bool("ALIYUN_RD_AUTO_DISCOVERY", default=False),
        "rd_manager_account_key": (os.environ.get("ALIYUN_RD_MANAGER_ACCOUNT_KEY") or "").strip().lower(),
        "load_error": load_error,
    }


def get_all_accounts() -> Dict[str, Dict]:
    global _accounts_cache

    if _accounts_cache is None:
        _accounts_cache = _load_accounts()

    return {
        account_key: {
            "account_key": account_key,
            "account_name": account_config.account_name,
            "default_region": account_config.default_region,
            "description": account_config.description,
            "uses_sts_role": bool(account_config.role_arn),
        }
        for account_key, account_config in _accounts_cache.items()
    }
