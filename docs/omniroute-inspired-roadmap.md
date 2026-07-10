# APISwitch OmniRoute-Inspired Roadmap

## 目标

APISwitch 继续坚持 **统一模型驱动**：客户端始终请求稳定的统一模型名，例如：

- `code-best`
- `chat-fast`
- `reasoning-best`
- `vision-cheap`

Provider、账号、节点、成本、额度、路由策略都属于统一模型内部实现，不直接暴露给普通客户端。

本路线参考 OmniRoute 的成熟设计，但适当精简，避免一次性引入过多子系统。

## 核心原则

1. **统一模型是一级入口**：所有协议最终解析到一个 Unified Model。
2. **Provider Connection 代表账号**：一个 Provider 可以配置多个 API Key、OAuth 账号或匿名免费账号。
3. **Provider Node 代表访问节点**：同一个账号可以使用不同区域、代理或兼容端点。
4. **Combo/Auto-Combo 是统一模型的内部路由模式**，不是新的客户端模型体系。
5. **评分因素精简为 8 项**，优先保证可解释性。
6. **成本、额度和会话粘性进入路由决策**。
7. **协议扩展复用统一执行管线**，避免每个接口各写一套路由逻辑。

## 一、Provider 扩充

不追求首阶段覆盖 200+ Provider，优先支持高价值、协议稳定、用户常见的 Provider。

### 第一批：直接 API Provider

- OpenAI
- Anthropic
- Google Gemini
- Azure OpenAI
- Google Vertex AI
- AWS Bedrock
- OpenRouter
- xAI
- Mistral
- Cohere
- DeepSeek
- Groq
- Together AI
- Fireworks AI
- SiliconFlow

### 第二批：中国区与开发者常用 Provider

- Alibaba DashScope / Qwen
- Zhipu / GLM
- Moonshot / Kimi
- Volcengine / Doubao
- MiniMax
- Baidu Qianfan
- Tencent Hunyuan
- ModelScope

### 兼容层

继续保留 `compatible` Provider，支持用户手动配置任意 OpenAI-Compatible 服务。

### Provider Catalog

后续增加静态 Provider Catalog，记录：

- Provider 类型与显示名称
- 默认 Base URL
- 支持协议
- 支持认证方式
- 是否支持 OAuth
- 是否有免费额度
- 是否支持额度查询
- 默认模型与能力标签

## 二、多账号、OAuth 和 Provider Node

已新增数据库基础表：

- `provider_connections`
- `provider_nodes`
- `model_pricing`
- `quota_snapshots`
- `usage_history`
- `session_affinity`

### Provider Connection

代表 Provider 下的一个账号或凭据：

- `auth_type`: `api_key` / `oauth` / `anonymous`
- 账号标签
- 加密凭据
- Refresh Token
- Token 过期时间
- 优先级
- 是否启用
- Provider-specific metadata

### Provider Node

代表实际请求节点：

- Base URL
- Region
- Connection 绑定
- 权重
- 能力标签
- 代理或区域信息

典型结构：

```text
Provider: OpenAI
  ├─ Connection: personal-key
  │    ├─ Node: official-us
  │    └─ Node: company-proxy
  └─ Connection: team-oauth
       └─ Node: official-sg
```

### OAuth 精简范围

首阶段只实现少量价值最高的 OAuth：

- Google / Gemini
- OpenAI / Codex 相关账号（在官方授权方式允许的前提下）
- Anthropic / Claude 相关账号（在官方授权方式允许的前提下）

其他 Provider 仍以 API Key 为主。

## 三、协议扩充

所有协议都必须经过：

```text
协议请求
  → 标准内部请求
  → Unified Model
  → Combo / Auto-Combo
  → Provider Connection + Node
  → Provider Adapter
  → 标准内部响应
  → 协议响应
```

### P0：核心文本与开发工具

- Chat Completions
- Responses，包括 Streaming
- Anthropic Messages
- Gemini `v1beta`
- Embeddings
- WebSocket 流式桥接

### P1：文件和多模态

- Files
- Images generations / edits
- Audio speech / transcriptions
- Moderations
- Rerank
- Search

### P2：异步和生成媒体

- Batches
- Video
- Music

首阶段可以返回标准 `not_supported_by_candidate` 错误，不要求所有 Provider 都支持每种协议。

## 四、统一模型内部的 Combo / Auto-Combo

Unified Model 增加三种内部路由模式：

### `static`

使用显式维护的 Candidate 列表，即当前实现。

### `combo`

使用显式 Candidate 列表，但允许选择路由策略：

- `priority`
- `weighted`
- `round_robin`
- `least_used`
- `cost_optimized`
- `quota_headroom`
- `last_known_good`

### `auto`

根据统一模型约束动态扫描所有可用 Provider Connection 和 Node，生成临时候选池。

统一模型可以定义：

- 类别：`chat` / `coding` / `reasoning` / `vision` / `multimodal` / `embedding`
- 档位：`fast` / `balanced` / `quality` / `cheap` / `free` / `reliable`
- 最大单请求成本
- 最大延迟
- 最小上下文窗口
- 必须支持的能力
- 是否启用会话粘性

客户端仍然请求统一模型，例如 `code-best`；不会直接请求 `auto/coding:cheap`。

## 五、精简自动评分

APISwitch 使用 8 因子评分，权重可在 Unified Model 中覆盖：

| 因子 | 默认权重 | 说明 |
|---|---:|---|
| Health | 0.25 | Circuit Breaker、近期成功率 |
| Quota | 0.15 | 剩余额度、限流余量 |
| Cost | 0.15 | 输入/输出价格与单请求预算 |
| Latency | 0.15 | p95 延迟和首 Token 延迟 |
| Task Fit | 0.10 | coding/reasoning/vision 等任务适配 |
| Context Fit | 0.08 | 上下文窗口适配 |
| Stability | 0.07 | 错误率和延迟波动 |
| Manual Priority | 0.05 | 用户手动偏好 |

总权重为 `1.00`。

### 路由流程

1. 按协议和能力过滤候选。
2. 排除 disabled、过期凭据和 open circuit。
3. 应用单请求预算上限。
4. 应用 Unified Model 类别和档位。
5. 检查会话粘性，优先 Last Known Good。
6. 计算自动评分。
7. 依次尝试候选并记录 Retry Chain。

### 单请求控制

计划支持：

- `X-APISwitch-Budget`: 单请求最大预计成本
- `X-APISwitch-Session`: 会话粘性 Key
- `X-APISwitch-Tier`: 临时指定 `fast` / `cheap` / `quality` 等档位

这些 Header 只能收紧统一模型策略，不能绕过统一模型安全约束。

## 六、价格、Token、额度和用量

### Model Pricing

记录每个 Provider/Model 的：

- 输入 Token 单价
- 输出 Token 单价
- Cached Input 单价
- 币种
- 生效时间

价格来源：

1. 用户手动覆盖
2. Provider 官方 Catalog
3. APISwitch 内置默认 Catalog

### Token Accounting

每个请求统一记录：

- 输入 Token
- 输出 Token
- Cache Token
- 估算成本
- Provider Connection
- Unified Model
- API Token
- 协议

### Usage History

`usage_history` 用于：

- 按小时/日/月统计
- Provider 成本对比
- Unified Model 成本对比
- API Token 成本归属
- Budget 自动累计

### Quota Snapshot

每个 Provider Connection 定期记录：

- 剩余请求数
- 剩余 Token
- 剩余 Credit
- Reset 时间
- 原始 Provider 响应

### Budget Enforcement

预算匹配顺序：

1. API Token Budget
2. Unified Model Budget
3. Provider Budget
4. Global Budget

超限行为可选：

- `reject`
- `fallback_to_free`
- `fallback_to_cheapest`
- `warn_only`

## 七、Claude Code 配置写入

已实现第一版：

- Admin API: `POST /api/admin/agents/claude-code/write`
- 前端 Agent 页面可预览和写入 Profile
- 默认写入 `~/.claude/profiles/<profile>/settings.json`
- 可通过 `APISWITCH_CLAUDE_CONFIG_ROOT` 更改根目录
- Existing `settings.json` 会先备份
- 使用临时文件进行原子替换
- Profile 名称有路径穿越校验
- 自动移除 Base URL 末尾的 `/v1`
- 写入：
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_MODEL`
  - `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`
  - 可选 Token 和压缩窗口配置
- **不会将 `ANTHROPIC_AUTH_TOKEN` 写入配置文件**
- 返回 PowerShell 和 POSIX 启动命令，由用户在启动时注入 APISwitch Token

示例生成内容：

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "code-best",
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080",
    "ANTHROPIC_MODEL": "code-best",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"
  }
}
```

## 八、实施顺序

### Phase A：稳定当前核心

- 跑通 `pytest`
- 跑通 `npm run test`
- 跑通 `npm run build`
- 替换占位 SecretCrypto
- Admin API 认证

### Phase B：Provider Connection 和 Node

- Connection CRUD
- Node CRUD
- 旧 Provider API Key 自动迁移成默认 Connection
- Provider Catalog
- 多账号轮换和健康检查

### Phase C：成本与 Auto-Combo

- Pricing CRUD / Catalog
- Token Accounting
- Usage History 写入
- Quota Snapshot
- 8 因子评分
- Session Affinity
- 单请求预算 Header

### Phase D：协议扩充

依次实现：

1. Responses Streaming
2. Embeddings
3. Gemini `v1beta`
4. Files
5. Images
6. Audio
7. Moderations / Rerank / Search
8. Batches / WebSocket
9. Video / Music

### Phase E：更多 Provider 与 OAuth

按用户需求和稳定性逐批加入，而不是一次性加入所有 Provider。
