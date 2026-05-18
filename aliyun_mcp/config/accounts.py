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

_accounts_cache: Optional[Dict[str, AccountConfig]] = None


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
    global _accounts_cache

    # Drop stale ALIYUN_ACCOUNT_* values from current process before reloading .env.
    for key in list(os.environ.keys()):
        if ACCOUNT_ENV_PATTERN.match(key):
            os.environ.pop(key, None)

    dotenv_path = os.environ.get("ALIYUN_DOTENV_PATH") or find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=True)

    _accounts_cache = None
    from aliyun_mcp.core.client_factory import clear_client_cache

    clear_client_cache()
    _load_accounts()


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
