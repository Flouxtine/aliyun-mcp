# Cursor / Claude Desktop MCP 注册

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

在 MCP 客户端中配置 **SSE URL**（具体字段名因客户端而异），通常为服务根路径下的 `/sse`（与 FastMCP 版本一致；若连接失败请用浏览器或 curl 查看服务返回的路由说明）。

## 验证

1. 在 Agent 中请求调用 `aliyun_list_configured_accounts`。
2. 再调用 `aliyun_get_account_info` 与 `aliyun_describe_vpcs` 做只读验证。

## RAM 权限

见同目录 `RAM_READONLY_EXAMPLE.json`，请按实际产品裁剪并遵循最小权限。
