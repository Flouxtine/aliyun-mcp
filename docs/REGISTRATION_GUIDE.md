# Cursor / Claude Desktop MCP 注册

如果接入的是飞书机器人、Bot 网关或远程 Agent，请优先看 [BOT_CONNECTION_GUIDE.md](BOT_CONNECTION_GUIDE.md)。这类场景通常需要 HTTP 常驻服务，不能只配置本地 stdio。

## stdio（推荐本地）

在 Cursor **Settings → MCP** 或项目 `.cursor/mcp.json` 增加：

```json
{
  "mcpServers": {
    "aliyun": {
      "command": "/ABS/PATH/aliyun_mcp/.venv/bin/python",
      "args": ["/ABS/PATH/aliyun_mcp/main.py"],
      "envFile": "/ABS/PATH/aliyun_mcp/.env"
    }
  }
}
```

将 `/ABS/PATH/aliyun_mcp` 替换为本仓库绝对路径。若不用 `envFile`，可把 `ALIYUN_ACCOUNT_*` 写在 `env` 对象中。

推荐：使用上面的 `command + args + envFile` 直连方式，不要通过 `run_mcp.sh` 或其他 shell 包装脚本启动。这样可减少客户端对本地命令执行的审批弹窗。

## 使用本机阿里云 CLI profile

MCP 支持两种方式读取本地 CLI profile：

- 显式指定：在 `.env` 中设置 `ALIYUN_ACCOUNT_{KEY}_CLI_PROFILE`
- 自动回退：未设置 `CLI_PROFILE` 时，按“账号 key -> default”尝试 profile

显式指定示例（例：`gmi-test`）：

```env
ALIYUN_ACCOUNT_GMI_CLI_PROFILE=gmi-test
ALIYUN_ACCOUNT_GMI_ACCOUNT_NAME=gmi-test
```

自动回退示例（不写 `CLI_PROFILE`，自动尝试 `gmi`、`default`）：

```env
ALIYUN_ACCOUNT_GMI_ACCOUNT_NAME=gmi-test
```

- 默认读取 `~/.aliyun/config.json`；自定义路径可设环境变量 **`ALIYUN_CLI_CONFIG_PATH`**。
- 仅支持 CLI 里 **`mode` 为 `AK`** 的 profile（与当前 MCP 从文件读 AK 的方式一致）。
- 若同时配置了 `.env` 中的 `ACCESS_KEY_*` / `DEFAULT_REGION`，则以 `.env` 为准（优先级更高）。

## HTTP / SSE

先启动：

```bash
python main.py --transport http --host 127.0.0.1 --port 8000
```

也可以使用项目内脚本：

```bash
./run_mcp_http.sh
```

在 MCP 客户端中配置 **SSE URL**（具体字段名因客户端而异），通常为服务根路径下的 `/sse`（与 FastMCP 版本一致；若连接失败请用浏览器或 curl 查看服务返回的路由说明）。

## 验证

1. 在 Agent 中请求调用 `aliyun_bootstrap_session`。
2. 再调用 `aliyun_get_account_count` 或 `aliyun_list_configured_accounts`。
3. 最后调用 `aliyun_get_account_info` 与 `aliyun_describe_vpcs` 做只读验证。

## Landing Zone / Resource Directory

项目账号较多时，推荐只配置一个 RD 管理账号，再开启自动发现：

```env
ALIYUN_ACCOUNT_RD_MANAGER_CLI_PROFILE=rd-manager
ALIYUN_ACCOUNT_RD_MANAGER_DEFAULT_REGION=cn-shanghai
ALIYUN_ACCOUNT_RD_MANAGER_ACCOUNT_NAME=资源目录管理账号

ALIYUN_RD_AUTO_DISCOVERY=true
ALIYUN_RD_MANAGER_ACCOUNT_KEY=rd_manager
ALIYUN_RD_ROLE_NAME=ReadOnlyForMcp
ALIYUN_RD_ROLE_SESSION_NAME=aliyun-mcp
ALIYUN_RD_ACCOUNT_KEY_PREFIX=rd
ALIYUN_RD_DEFAULT_REGION=cn-shanghai
```

要求：每个子账号中都需要存在同名角色（如 `ReadOnlyForMcp`），并信任 RD 管理账号扮演。修改 `.env` 后可调用 `aliyun_reload_account_configs`，必要时重连 MCP 服务。

## RAM 权限

见同目录 `RAM_READONLY_EXAMPLE.json`，请按实际产品裁剪并遵循最小权限。
