# LightClaw

LightClaw 是一个受 OpenClaw 风格启发的轻量级个人 AI Agent 框架。

## 当前状态

当前仓库已经包含：

- `src/lightclaw` 下的模块化 Python 代码
- FastAPI 和 CLI 入口
- 基于 SQLite 的持久化
- OpenAI-compatible、Anthropic 和 mock provider
- 基于 schema 的工具框架
- Telegram 集成
- 结构化 memory 与自动提取流程
- jobs 和 scheduler
- declarative skills
- 基于 manifest 的 MCP 工具加载

## 推荐环境方式

当前项目已经调整为 **优先使用 `uv` 管理隔离环境**。

在你这台机器上，已经验证通过的工作方式是：

1. 用 `uv` 创建并维护项目自己的 `.venv`
2. 用脚本启动项目，而不是手动把依赖混到全局环境
3. 项目源码通过 `PYTHONPATH=src` 运行

也就是说，现在推荐你始终使用仓库里的 PowerShell 脚本。

## Windows PowerShell 启动步骤

### 1. 初始化隔离环境

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-init.ps1
```

这一步会完成：

- 用 `uv` 创建 `.venv`
- 生成或更新 `uv.lock`
- 用 `uv sync --extra dev --no-install-project` 安装第三方依赖
- 如果没有 `.env`，则从 `.env.example` 自动复制
- 执行数据库迁移

### 2. 检查数据库状态

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
```

正常情况下你会看到：

- `current_version` 与 `latest_version` 一致
- `pending_versions=none`

### 3. 启动 API 服务

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-api.ps1
```

默认地址：

- `http://127.0.0.1:8000`

### 3.1 打开前端控制台

启动 API 后，直接打开：

- `http://127.0.0.1:8000/console`

当前控制台已经支持：

- 配置 provider 和运行策略
- 首次启动向导和本地登录
- 在浏览器里直接聊天
- 流式对话输出
- 查看会话历史
- 管理 jobs 和 scheduler
- 本地用户管理和按用户隔离的控制台资源
- 查看 skills 与 tools
- provider 连通性测试
- 查看执行日志
- 查看系统与 migration 状态

这里的 `openai_compatible` 意思是“兼容 OpenAI API 格式”，不是“只能接 OpenAI 官方”。

因此它可以接：

- OpenAI
- OpenRouter
- 自建或第三方 OpenAI-compatible 网关

例如接 OpenRouter 时，可以这样配：

```env
LIGHTCLAW_PROVIDER_BACKEND=openai_compatible
LIGHTCLAW_PROVIDER_BASE_URL=https://openrouter.ai/api/v1
LIGHTCLAW_PROVIDER_MODEL=openai/gpt-4o-mini
LIGHTCLAW_PROVIDER_API_KEY=你的 OpenRouter Key
LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON={"HTTP-Referer":"https://your-app.example","X-Title":"LightClaw"}
```

### 4. 在另一个终端测试 CLI

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "hello"
```

进入交互模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 repl
```

## 基础验收命令

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

发送一条 API 对话请求：

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"demo\",\"user_id\":\"demo-user\",\"message\":\"hello\",\"channel\":\"api\"}"
```

查看 skills：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 skills list
```

执行一个工具：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "/tool echo.text hello-tool"
```

## 数据库相关命令

迁移文件目录：
[src/lightclaw/infrastructure/persistence/migration_files](/E:/西电/研二/dmx/lightClaw/src/lightclaw/infrastructure/persistence/migration_files)

常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db migrate
```

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Docker

构建镜像：

```powershell
docker build -t lightclaw:local .
```

运行镜像：

```powershell
docker run --rm -p 8000:8000 lightclaw:local
```

## 更多文档

- 本地运行说明：[docs/planning/06-local-runbook.md](/E:/西电/研二/dmx/lightClaw/docs/planning/06-local-runbook.md)
- 开发路线图：[docs/planning/05-implementation-roadmap.md](/E:/西电/研二/dmx/lightClaw/docs/planning/05-implementation-roadmap.md)
- English README：[README.md](/E:/西电/研二/dmx/lightClaw/README.md)
