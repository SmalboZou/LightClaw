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

当前项目推荐：

1. 使用 `uv` 管理隔离的 `.venv`
2. 通过 `PYTHONPATH=src` 从源码运行
3. 优先使用仓库内脚本，而不是手工激活环境后再拼命令

## Windows 快速开始

### 1. 初始化环境

```powershell
.\scripts\dev-init.cmd
```

这一步会：

- 创建或修复 `.venv`
- 复制 `.env.example` 到 `.env`
- 通过 `uv sync --extra dev` 安装依赖
- 执行数据库迁移

### 2. 检查数据库状态

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
```

期望看到：

- `current_version` 与 `latest_version` 一致
- `pending_versions=none`

### 3. 启动 API

```powershell
.\scripts\run-api.cmd
```

这条命令会以前台方式运行 Uvicorn。终端不会自动返回提示符，这是正常行为，不代表“卡死”。

已验证可用的底层启动命令是：

```powershell
.\.venv\Scripts\python.exe -m uvicorn lightclaw.main:app --factory --host 127.0.0.1 --port 8000 --app-dir .\src
```

只有看到下面这行时，才表示 API 已经真正启动完成：

```text
Uvicorn running on http://127.0.0.1:8000
```

默认本地入口：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/console`
- `http://127.0.0.1:8000/docs`

### 4. 打开 Web Console

API 启动后，直接访问：

- `http://127.0.0.1:8000/console`

### 5. 在另一个终端测试 CLI

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "hello"
```

交互模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 repl
```

## 基础验证

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

聊天请求：

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"demo\",\"user_id\":\"demo-user\",\"message\":\"hello\",\"channel\":\"api\"}"
```

列出 skills：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 skills list
```

运行一个工具：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "/tool echo.text hello-tool"
```

如果你不确定 API 是否真的启动，不要用“当前终端有没有返回提示符”来判断。应该在另一个终端里检查：

```powershell
curl http://127.0.0.1:8000/health
```

或者：

```powershell
netstat -ano | findstr :8000
```

## 数据库命令

迁移文件目录：
[src/lightclaw/infrastructure/persistence/migration_files](/E:/西电/研二/dmx/lightClaw/src/lightclaw/infrastructure/persistence/migration_files)

常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db migrate
```

## 测试

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
