# APISwitch 已确认需求基线

> 状态：已确认；后续设计、开发、测试和任务拆分均以此为产品基线。  
> 更新：2026-07-14。详细架构与实施方案见 [OmniRoute 启发路线图](omniroute-inspired-roadmap.md)。

## 产品定位

APISwitch 是 **Windows 优先、本地优先、可部署到服务器的 AI API 网关和管理后台**。它给客户端提供稳定的统一模型名，内部负责 Provider、账号、节点、价格、额度、健康度、故障切换与审计。

它参考 OmniRoute 的成熟能力，但不复制其全部复杂度；目标是更轻量、Python 原生、可审计、适合个人和小团队自托管。

## 不变的核心原则

1. **统一模型驱动**：客户端始终请求 `code-best`、`chat-fast`、`reasoning-best` 等 Unified Model，不直接选择 Provider、账号、节点或 `auto/...` 模型。
2. **Combo/Auto-Combo 是 Unified Model 的内部路由方式**，只改善候选选择，不替换统一模型入口。
3. **每阶段可运行、可验证**：迁移、测试、前端构建和关键接口必须真实执行通过。
4. **Windows 优先**：CLI 服务优先；后续支持前端托管、Docker、托盘和 Windows 服务。
5. **安全默认**：密钥、OAuth token、WebDAV 密码不得明文保存或回显；默认不保存完整 Prompt/Response。
6. **可解释性**：选择、跳过、重试、熔断和预算拦截须能从日志/API/UI 说明原因。

## 技术与协作约束

| 范围 | 已确认选择 |
|---|---|
| 后端 | Python、FastAPI、SQLAlchemy、Alembic、SQLite |
| 前端 | Vue 3、TypeScript、Vite、Naive UI、Pinia、Vue Router |
| 依赖管理 | `pip + requirements.txt` |
| 架构 | 模块化单体；Provider、协议、文件解析、Agent 保留插件扩展点 |
| 协作 | 默认直接提交 `main`，不创建 PR；任务需可交给 Codex/Agent 执行 |
| 质量门槛 | 后端 pytest、前端测试和前端构建是相应阶段的完成条件 |

## 功能需求

### 1. Provider、账号、节点

扩展 Provider Catalog，但不以“数量”代替质量。第一批：OpenAI、Anthropic、Gemini、Azure OpenAI、Vertex AI、AWS Bedrock、OpenRouter、xAI、Mistral、Cohere、DeepSeek、Groq、Together AI、Fireworks AI、SiliconFlow。第二批：中国区与开发者常用 Provider：DashScope/Qwen、Zhipu/GLM、Moonshot/Kimi、Volcengine/Doubao、MiniMax、Baidu Qianfan、Tencent Hunyuan、ModelScope。持续保留通用 `compatible` Provider。

Catalog 至少维护默认 Base URL、认证方式、支持协议、能力、OAuth、免费额度、额度查询与模型标签。

一个 Provider 可有多个 **Provider Connection**（API Key、OAuth 或匿名/免费账号）；每个 Connection 可有多个 **Provider Node**（区域、代理、兼容端点、Base URL、权重）。Unified Model 候选可绑定具体 Connection 和 Node。

OAuth 首期实现 Google/Gemini；OpenAI/Codex、Anthropic/Claude 仅在官方授权机制允许时加入。免费额度仅作为合法且可观测的路由资源，不绕过 Provider 的账号、地区或使用规则。

### 2. 网关协议与能力

所有协议必须使用同一执行管线：

```text
协议请求 → 内部标准请求 → Unified Model → 路由/候选 → Connection/Node
→ Provider Adapter → 内部标准响应 → 协议响应
```

| 优先级 | 范围 |
|---|---|
| P0 | Chat Completions、Responses（含 Streaming）、Anthropic Messages、Gemini `v1beta`、Embeddings、WebSocket 流式桥接 |
| P1 | Files、Images generations/edits、Audio speech/transcriptions、Moderations、Rerank、Search |
| P2 | Batches、Video、Music |

候选不支持某能力时，必须继续选择兼容候选或返回结构化 `not_supported_by_candidate`，不得伪造成功。

### 3. Unified Model、Combo、Auto-Combo

- `static`：显式维护 Candidate 列表。
- `combo`：显式 Candidate 列表，依策略调度。
- `auto`：依据统一模型约束扫描可用 Connection/Node/发现模型，维护动态候选池。

统一模型可定义类别（chat/coding/reasoning/vision/multimodal/embedding）、档位（fast/balanced/quality/cheap/free/reliable）、所需能力、最大单请求成本、最大延迟、最小上下文窗口与会话粘性。

Combo 策略至少包括：`priority`、`weighted`、`round_robin`、`least_used`、`cost_optimized`、`quota_headroom`、`last_known_good`。`X-APISwitch-Budget`、`X-APISwitch-Session`、`X-APISwitch-Tier` 只能收紧该 Unified Model 的规则，不能绕过安全和预算约束。

### 4. 自动评分、可靠性、会话粘性

默认八因子评分可由 Unified Model 覆盖：

| 因子 | 权重 |
|---|---:|
| Health（熔断、近期成功率） | 0.25 |
| Quota（额度/限流余量） | 0.15 |
| Cost（价格/单请求预算） | 0.15 |
| Latency（p95/首 Token） | 0.15 |
| Task Fit | 0.10 |
| Context Fit | 0.08 |
| Stability | 0.07 |
| Manual Priority | 0.05 |

路由顺序：能力过滤 → disabled/过期凭据/open circuit 过滤 → 预算过滤 → 类别/档位过滤 → 会话粘性 → 评分 → 重试链记录。保留 Circuit Breaker 的 `closed/open/half_open` 状态机。

### 5. 价格、用量、额度、预算

- **Model Pricing**：输入、输出、缓存 Token 价格、币种和生效时间；优先级为用户覆盖、Provider Catalog、内置目录。
- **Token Accounting**：每次请求记录输入/输出/缓存 Token、估算成本、Unified Model、Provider、Connection、API Token 和协议。
- **Usage History**：按小时/日/月统计；可按 Provider、Unified Model、API Token 对比成本。
- **Quota Snapshot**：按 Connection 保存剩余请求、Token、Credit、重置时间和 Provider 原始响应。
- **Budget Enforcement**：匹配顺序 API Token → Unified Model → Provider → Global；超限动作为 `reject`、`fallback_to_free`、`fallback_to_cheapest`、`warn_only`。

这些数据必须影响路由或拦截，不能仅停留在 CRUD/UI。

### 6. 管理后台与审计

后台必须管理 Provider、Connection、Node、发现模型、Unified Model/Candidate、路由健康、日志、价格、额度、用量、预算、Token、WebDAV、Agent 与系统设置。

日志至少包含协议、统一模型、最终 Provider/Connection/Node/上游模型、评分或策略、重试链、Token、估算成本、延迟、首 Token 延迟、预算决定、失败原因和熔断状态。

### 7. Claude Code 配置写入

必须实现实际写入能力：检查路径、预览、备份、原子写入，以及后续的备份恢复。默认写入 `~/.claude/profiles/<profile>/settings.json`，可由 `APISWITCH_CLAUDE_CONFIG_ROOT` 覆盖。生成 `ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`、`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`，并移除 Base URL 尾部 `/v1`。

不能把 APISwitch Token 写入文件；应返回 PowerShell/POSIX 启动命令，让用户运行时注入 Token。Profile/路径必须防路径穿越，旧配置必须先备份。

### 8. WebDAV、安全与部署

WebDAV 需完成加密配置导入/导出、差异预览、导入前数据库备份、冲突处理、同步日志和可选定时同步。现有 Profile CRUD/连接测试只是基础。

用 Windows DPAPI/Credential Manager 或跨平台 `APISWITCH_MASTER_KEY` 强加密替换占位 SecretCrypto；`/v1/*` 继续使用带 scope、过期、启停和审计的 Bearer Token，并补齐 Admin API 认证或可靠本机访问保护。最终支持 FastAPI 托管前端、Windows CLI 打包和 Docker。

## 非目标

1. 首版不逐项复制 OmniRoute 的 Provider 规模、Agent、记忆或压缩子系统。
2. 不绕过 Provider 的 OAuth、免费额度、地域或使用限制。
3. 不把多租户/SaaS 权限体系作为首版核心。
4. 不以新增协议为由破坏统一模型、鉴权、日志或错误语义。

## 实施顺序与验收

1. 质量与安全：真实跑通测试/构建，完成密钥加密和 Admin 防护。
2. Provider 基座：Catalog、Connection、Node、多账号、Gemini OAuth、健康检查与模型发现。
3. 成本路由：价格、完整用量、Quota Snapshot、八因子评分、会话粘性、预算动作。
4. P0 协议：稳定 Responses Streaming、Anthropic Messages、Gemini `v1beta`、Embeddings、WebSocket。
5. P1/P2：按 Provider 能力逐项实现多模态、异步及媒体协议。
6. 操作体验：Claude Code 备份恢复/自动扫描、WebDAV 完整同步、Windows/Docker 发布。

每项任务完成必须具备：可执行迁移、接口与错误语义测试、可用前端交互、同步文档，并通过适用的 `pytest`、`npm run test`、`npm run build`。

## 变更规则

后续需求以本文为准。增加 Provider、协议或路由策略时，必须同时说明其服务的 Unified Model 能力、认证方式、支持协议、价格/额度可观测性、失败与降级行为，以及可执行的验收测试。
