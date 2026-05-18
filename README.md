# 阿里云多账号 MCP

基于 [FastMCP](https://github.com/jlowin/fastmcp) 的多账号阿里云只读 MCP 服务，结构与 `aws_mcp` 对齐：环境变量多账号、`stdio`/`http` 双传输、工具强制 `account` 参数、Prompts/Resources 分层。

## 功能

- 多账号：`ALIYUN_ACCOUNT_{KEY}_*`，可选 `ROLE_ARN` + `ROLE_SESSION_NAME`（STS 扮演 RAM 角色）
- **本机阿里云 CLI profile**：
	- 可显式设置 `ALIYUN_ACCOUNT_{KEY}_CLI_PROFILE=profile名`
	- 未设置时会自动尝试本地 profile：先按账号 key（如 `staging`），再尝试 `default`
	- 读取来源为 `~/.aliyun/config.json`（或 `ALIYUN_CLI_CONFIG_PATH`），仅支持 **mode=AK**
	- `.env` 里已写的 `ACCESS_KEY_*` / `DEFAULT_REGION` 优先于 profile 同字段
- 只读工具：ECS `DescribeInstances`、VPC `DescribeVpcs`、标签 `ListTagResources` / `ListSupportResourceTypes`
- 账单：`QueryBillOverview`
- 监控：云监控 `DescribeAlertHistoryList`
- 审计：ActionTrail `LookupEvents`
- 账号描述、区域与运维常量的 MCP Resources；中文 Prompt 模板

## 环境要求

- Python **3.10+**（推荐使用 3.11，可用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境）

## 安装

```bash
cd aliyun_mcp
uv venv -p 3.11
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
```

## 配置

复制 `.env.example` 为 `.env` 并填写 AccessKey（建议使用 **仅只读权限** 的 RAM 用户或 STS 角色）。

```bash
cp .env.example .env
```

如需使用本地阿里云 CLI 配置，可二选一：

- 显式指定 profile：`ALIYUN_ACCOUNT_STAGING_CLI_PROFILE=prod-ops`
- 不指定 profile：MCP 自动尝试 `staging` 与 `default`

## 启动

**stdio（Cursor 本地 MCP）：**

```bash
python main.py
```

**HTTP：**

```bash
python main.py --transport http --host 0.0.0.0 --port 8000
```

安装后的入口命令（若 PATH 可用）：

```bash
aliyun-mcp
```

## 接入 Agent

见 [docs/REGISTRATION_GUIDE.md](docs/REGISTRATION_GUIDE.md) 与 RAM 只读策略示例 [docs/RAM_READONLY_EXAMPLE.json](docs/RAM_READONLY_EXAMPLE.json)。

## Docker

```bash
docker build -t aliyun-mcp:latest .
docker run --rm -p 8000:8000 --env-file .env aliyun-mcp:latest --transport http --host 0.0.0.0 --port 8000
```

## 安全说明

- 勿将 `.env` 提交到仓库；生产环境优先 **STS AssumeRole** + 最小只读策略。
- 工具返回可能含内网 IP、资源 ID，请勿随意外发。
# aliyun-mcp
