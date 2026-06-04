# Bot 接入与排障指南

## 现象

如果 bot 回复“当前不能直接调用阿里云 MCP”“工具列表里没有 aliyun MCP”“只能提供 CLI/API 命令”，通常不是 MCP 代码逻辑问题，而是当前会话没有成功挂载这个 MCP server。

## 推荐接入方式

### 本地 IDE / Cursor / Claude Desktop

使用 stdio 直连，不要通过 shell 包装脚本：

```json
{
  "mcpServers": {
    "aliyun": {
      "command": "/Users/zane/Downloads/aliyun_mcp/.venv/bin/python",
      "args": ["/Users/zane/Downloads/aliyun_mcp/main.py"],
      "envFile": "/Users/zane/Downloads/aliyun_mcp/.env"
    }
  }
}
```

### Bot 网关 / 飞书机器人 / 远程 Agent

这类 bot 通常不能直接使用本机 stdio，需要把 MCP 作为 HTTP 常驻服务接入。

启动服务：

```bash
cd /Users/zane/Downloads/aliyun_mcp
./run_mcp_http.sh
```

或直接：

```bash
/Users/zane/Downloads/aliyun_mcp/.venv/bin/python /Users/zane/Downloads/aliyun_mcp/main.py --transport http --host 0.0.0.0 --port 8000
```

然后在 bot 网关中配置该 MCP 的 HTTP/SSE 地址。具体路径取决于网关和 FastMCP 版本，常见为服务根地址或 `/sse`。如果网关支持 MCP streamable HTTP，优先按网关文档填写。

## 首次验证

连接成功后，不要先问业务问题，先让 bot 调用：

```text
aliyun_bootstrap_session
```

然后验证账号：

```text
aliyun_get_account_count
aliyun_get_config_diagnostics
```

成功时应看到：

- `mcp_service: up`
- `accounts_ready: true`
- `loaded_account_keys` 包含 `.env` 中配置的账号，例如 `gmi_infra`、`anchnet_test`

## 如果 bot 还是不能直接用

按顺序检查：

1. bot 当前会话工具列表中是否出现 `aliyun_*` 或带前缀的 `mcp_...aliyun...` 工具。
2. MCP 服务进程是否在运行。
3. bot 网关配置的是不是当前项目路径或当前 HTTP 地址。
4. 修改 `.env` 后是否调用过 `aliyun_reload_account_configs` 或重启过 MCP。
5. bot 是否把 terminal/read_file/browser 权限当作替代工具。若是，当前 MCP 没挂上，不要继续让它跑本地命令。

## 避免 Command Approval Required

业务查询、报表、账号诊断都应该走 MCP 工具：

- 账号诊断：`aliyun_get_config_diagnostics`
- 会话自检：`aliyun_bootstrap_session`
- 当前时间：`aliyun_get_current_time`
- 资源概览：`aliyun_get_account_resource_snapshot`
- Word 报告：`aliyun_generate_report_docx`
- PPT 报告：`aliyun_generate_report_pptx`
- PDF 报告：`aliyun_generate_report_pdf`
- HTML 报告：`aliyun_generate_report_html`
- CSV 报表：`aliyun_generate_report_csv`

不要让 bot 执行：

- terminal / shell
- `date` 命令
- execute_code / notebook / 通用代码执行
- `python -c` / `python3 -c`
- `pip install` / `pandoc` / openpyxl 本地文档脚本
- write_file 生成 Word/PPT/PDF/HTML/Excel 报告
- 读取 `~/.hermes/*`、`~/.aliyun/*` 等宿主配置

如果 bot 消息里仍出现 `terminal`、`execute_code`、`python`、`date`，说明当前 bot 没有完全遵循 MCP 运行策略，建议停止该轮任务并重新发起：

```text
只使用 aliyun_mcp 的 MCP 工具；当前时间调用 aliyun_get_current_time；报告文件调用 aliyun_generate_report_*；禁止 terminal、execute_code、python、date、write_file。
```
