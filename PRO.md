# 个人AI代理框架（类Nanobot）产品说明与需求文档 (PRD)

## 一、 产品概述
**产品名称**：[待定]（类Nanobot个人代理框架）  
**产品定位**：一款开箱即用、高度可扩展的全能型个人AI智能体（Agent）产品（对标OpenClaw），兼具极客的自定义能力与普通用户的使用便利性。
**核心理念**：以极简的代码架构提供强大的Agent核心循环（Agent Loop），采用“自带密钥（BYOK）”模式，用户只需提供任意受支持的LLM服务商API Key（如OpenAI、Claude等），即可驱动前端无缝接入的各类日常通讯软件或自定义客户端。让AI像真人助理一样，拥有执行各种操作的能力。
**产品愿景**：不仅仅是开发者的基础设施，更是普通人触手可及的“数字分身与全能助理”，只需一次简单部署并填入自己的LLM API，即可在熟悉的聊天软件中即开即用。

---

## 二、 目标用户与使用场景
### 1. 目标用户
- **普通大众用户**：零代码基础，在系统由他人或一键部署完成后，只需输入个人持有的LLM服务商API Key（如OpenAI API Key、Kimi API Key等），即可在其熟悉的微信、TG等聊天工具中以自然语言交互，享受开箱即用的专属AI助理服务，没有任何额外成本。
- **开发者/创作者**：拥有编程能力，既能自己私有化部署，也能开发新插件（Skills）、MCP服务等以扩展AI能力边界。
- **团队/企业管理者**：将系统集中部署并配置好团队公用的LLM API，作为企业微信、飞书等群聊的协同大脑，处理内部服务与信息汇总。

### 2. 核心场景
- **全端协同助理**：在Telegram、微信、Slack中随时呼叫AI，利用其长记忆特性处理跨平台的工作。
- **自动化工作流**：让AI根据Cron定时任务主动去抓取数据、总结昨天的工作，并通过消息总线发送到对应的渠道。
- **代码与运维管理**：通过赋予GitHub、Shell工具权限，让AI在后端直接操作终端执行部署或拉取代码审查。

---

## 三、 核心需求分析（Functional Requirements）

### 1. LLM 引擎与大脑 (Agent & Providers)
- **多模型无缝切换**：支持OpenAI结构、Anthropic (Claude)、Azure以及本地模型（通过兼容API，如llama.cpp）。
- **心智循环机制 (Agent Loop)**：支持 `思考(Think)` -> `行动(Action/Tool)` -> `观察(Observe)` -> `回复(Reply)` 的标准代理循环机制。
- **动态系统提示词 (Prompt Context)**：整合角色定义（Identity）、长期记忆（Memory）以及启用的技能（Skills），动态生成给各模型的System Prompt。

### 2. 交互渠道接入 (Channels Integration)
- **核心能力**：需要一套统一的渠道适配器（Base Channel）和消息总线（Message Bus），解耦业务逻辑和平台特性。
- **必选接入渠道**：CLI命令行终端、API Gateway（RESTful API）、Telegram、Slack、飞书、钉钉、企业微信、Discord等。
- **特殊渠道支持**：WhatsApp（通过Node.js/Bridge独立处理）及基于WebSocket的实时前端对接。

### 3. 工具与技能系统 (Tools & Skills mechanism)
- **内置工具链 (Tools)**：
  - 文件系统操作（读、写、修改）
  - Shell命令执行映射
  - Web搜索与网页内容抓取（DuckDuckGo、Readability等）
- **技能拓展系统 (Skills)**：
  - 基于Markdown+YAML的声明式技能注册机制。
  - 支持技能依赖检测（环境变量、系统CLI命令检测）。
  - 支持 “始终加载 (Always Active)” 与 “按需加载 (Dynamic Content)” 的模块化能力挂载。
- **MCP 协议支持**：兼容标准 Model Context Protocol 连接外部工具和服务。

### 4. 记忆与会话管理 (Memory & Session)
- **会话持久化**：以本地/数据库形式保存多渠道各用户的对话历史，支持自动上下文截断以防止Token超限。
- **长期记忆提取**：AI能够自主决定将关键信息提炼并写入记忆文件（Memory Storage），在下次对话时自动挂载。

### 5. 心跳与定时调度 (Cron & Heartbeat)
- **基于Croniter的调度器**：支持让AI在后台自主运行设定好的定时任务。
- **心跳机制**：维持系统守护进程的健康运转以及长连接的存活，防止进程僵死。

---

## 四、 非功能性需求 (Non-Functional Requirements)

1. **超轻量与易维护性**：
   - 尽量减少重量级的框架依赖（如Langchain等），采用原生或轻量替代库。
   - 代码行数和模块耦合度尽量降到最低，追求高内聚低耦合。
2. **异步与并发**：
   - 全局须采用 `async/await` 异步架构处理高并发的网络请求（Aiohttp、httpx）。
3. **安全性设计**：
   - 需要提供沙箱隔离的概念或是权限白名单（尤其在执行系统 Shell 和 File IO 时）。
   - 涉密信息（API Keys、Tokens）统一由分离的Config及环境变量严格管理。
4. **自带密钥（BYOK）的极简部署（极易上手）**：
   - 包含一键部署方案（如 Dockerfile、Docker Compose 等），将复杂的环境配置与依赖管理封装。
   - 配置化极简，对于普通使用者，只需要填写相应的 `[LLM_API_KEY]` 和其个人聊天软件的 `[BOT_TOKEN]` 即可拉起服务，省去一切开发配置过程。

---

## 五、 系统架构规划设计

项目工程结构建议遵循清晰的分层架构（如同Nanobot）：

- **基础设施层**：各类 Provider SDK、数据库、网络驱动
- **通信总线层**：异步消息队列 (Queue & Event Bus)
- **核心业务层**：包括 `AgentRunner`、`Memory`、`SkillLoader` 和 `Hooks`
- **应用接口层**：`API Gateway`、`Channels Manager`（各类机器人 Webhook）以及 `CLI`（Typer指令）

---

## 六、 迭代计划与路线图 (Roadmap)

### Phase 1：MVP阶段（核心闭环）
- 搭建基础架构与目录设计。
- 完成CLI渠道对接与Agent核心处理逻辑开发。
- 接入1-2个云端LLM驱动（OpenAI, Anthropic）。
- 实现基础工具（Shell、文件读写）。

### Phase 2：多端触达与记忆进化
- 接入主要的IM平台（Telegram、飞书、企业微信等），建立统一的消息转换格式（Inbound/Outbound Message）。
- 建立并完善 Session History 管理。
- 引入长期记忆机制，使模型能记录并参考用户习惯。

### Phase 3：高级拓展与MCP引擎
- 完成声明式技能（Skills）体系搭建。
- 接入 MCP 服务器支持。
- 完善 Web 内容抓取、DuckDuckGo搜索等能力。
- 添加后台Cron定时任务与Heartbeat心跳保活模块。

---

> **附言**：该产品文档已为您全面提炼了基于Nanobot框架的程序构建需求和架构全景，可作为您后续编码实现和任务拆解的总指导方针。