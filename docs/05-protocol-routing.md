# 协议、路由与辅助模型

## 1. 统一协议内核

所有入口使用同一条执行管线，不允许各 API 复制独立路由逻辑。

```text
Ingress Adapter
→ Canonical Request
→ Capability Planner
→ Auxiliary Planner/Executor
→ Unified Model Router
→ Egress Adapter
→ Provider
→ Canonical Response/Event Stream
→ Ingress Response Adapter
```

## 2. 对外端点范围

| 协议 | 目标端点 |
|---|---|
| OpenAI Chat | `POST /v1/chat/completions` |
| OpenAI Responses | `POST /v1/responses` |
| Anthropic Messages | `POST /v1/messages` |
| Gemini | `/v1beta/models/{model}:generateContent`、`:streamGenerateContent` |
| Embeddings | `POST /v1/embeddings` |
| Files | `/v1/files` |
| Images | `/v1/images/generations`、`edits`、`variations` |
| Audio | `/v1/audio/speech`、`transcriptions` |
| Moderations | `POST /v1/moderations` |
| Rerank | `POST /v1/rerank` |
| Search | `POST /v1/search` |
| Batches | `/v1/batches` |
| WebSocket | `/v1/ws/chat/completions` 或最终契约定义路径 |
| Video | `/v1/videos/generations` 及状态查询 |
| Music | `/v1/music/generations` 及状态查询 |

全部模型字段指向统一模型。Files 可作为网关本地资源被其他请求引用。

## 3. Canonical Request

规范对象必须保留：

- 请求类型和入口协议
- 统一模型名
- message/content part 结构
- system/instructions
- 工具定义、选择、调用、结果
- 图片、文件、音频和 URL/base64 引用
- 生成参数和结构化输出约束
- 流式标志
- 路由收紧参数：预算、会话、档位
- 请求所需输入/输出能力

转换过程中不支持的字段不能静默丢弃。允许安全忽略的字段必须记录 warning；会改变语义的字段返回 `protocol_conversion_unsupported`。

## 4. 能力模型

建议拆分输入和输出能力：

- 输入：text、vision、files、audio、video、tool_results、long_context
- 输出：text、tools、json、embeddings、images、audio、video、music、moderation、rerank、search

统一模型能力是候选能力和辅助工作流能够共同满足的声明。每次请求仍进行动态校验。

## 5. Combo 路由

顺序：

1. 过滤禁用或远端不可用模型。
2. 过滤协议不兼容和能力不足模型。
3. 过滤过期凭据、开放熔断和预算超限模型。
4. 应用会话粘性。
5. 根据统一模型的 Combo 策略排序。
6. 调用候选并记录每次尝试。

策略：priority、weighted、round_robin、least_used、cost_optimized、quota_headroom、last_known_good。`auto` 模式也只能从已启用的上游模型中产生候选，不能扫描模板或未配置供应商。

## 6. 协议转换矩阵

路由状态页由后端返回矩阵，而不是前端硬编码。每一项状态为：

- `native`：上游原生支持。
- `lossless`：可等价转换。
- `assisted`：必须经过辅助工作流。
- `unsupported`：不能可靠执行。

矩阵同时考虑供应商协议和具体模型能力。开启统一模型入口协议不会把 `unsupported` 自动变为可用。

## 7. 流式处理

- 统一内部事件：start、content_delta、tool_delta、usage、completed、error。
- 在首个客户端事件前允许候选故障切换。
- 已发送流事件后不得重新从头切换造成重复内容。
- 流中错误转换为入口协议对应的错误事件，并记录失败阶段。
- WebSocket 与 SSE 共用事件生成器。

## 8. 辅助模型规划

### 8.1 模式

- `disabled`：缺少能力立即报错。
- `per_unified_model`：只搜索当前统一模型的辅助配置。
- `global_pool`：搜索全局池，默认。

### 8.2 预设工作流

| 工作流 | 示例 |
|---|---|
| vision_to_text | 图片先由视觉模型描述，再交主模型 |
| file_extract | 文件解析/摘要后写入主模型上下文 |
| context_compress | 长上下文压缩到主模型窗口内 |
| tool_plan | 辅助模型生成工具调用，结果回填主模型 |
| audio_transcribe | 音频转文本后交主模型 |
| structured_repair | 对输出进行结构化校验和修复 |
| terminal_capability | Embedding、图片、语音、视频、音乐等由辅助模型直接产生终端结果 |

工作流由有序步骤组成，每步声明输入能力、输出能力、超时和选模规则。不可组合的终端任务不能伪装成主模型能力。

### 8.3 失败

辅助步骤失败立即停止，返回：workflow ID、step index、辅助上游模型、错误类型和脱敏消息。不得自动寻找未配置模型。

本批日志只记录工作流、步骤状态和失败阶段；逐步骤 Token、成本、延迟及预算归集延期。

## 9. 路由测试台

测试 API 接收入口协议、统一模型和示例请求，返回：

- 入口原文
- Canonical Request
- 能力差距
- 规划的辅助链
- 候选排序及原因
- 选中供应商协议下的上游请求
- Mock 上游响应
- 最终入口响应

默认 dry-run，不调用真实供应商；显式选择真实测试时才允许调用。
