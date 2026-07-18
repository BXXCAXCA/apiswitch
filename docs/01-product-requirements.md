# 产品需求

## 1. 产品定位

APISwitch 是 Windows 优先、本地优先的 AI API 聚合网关和模型路由器。它把“供应商实例、上游模型、统一模型、辅助模型、客户端 Token”拆成清晰的业务层，让用户不需要理解账号节点、内部适配器或协议转换细节。

核心目标：

- 一个稳定网关地址服务多个客户端和 Agent。
- 同一供应商可以配置多个不同 API Key，并显示为多个独立供应商实例。
- 上游模型从具体供应商实例拉取，也允许手工维护。
- 统一模型绑定多个上游模型并应用 Combo 策略。
- 一个统一模型可以同时开启多个对外协议。
- 主模型缺少能力时，按明确配置调用辅助模型工作流。
- 所有敏感信息只在本机加密保存或加密备份。

## 2. 产品原则

1. **业务层级扁平**：取消独立的 Provider Connection 和 Provider Node 页面。
2. **模板不等于实例**：模板只提供默认值，填写凭据并启用后才创建供应商实例。
3. **能力显式**：模型和协议能力必须声明；不兼容时返回明确错误。
4. **不隐式替换统一模型**：缺少能力时只使用已配置的辅助工作流，不自动寻找其他统一模型。
5. **可解释路由**：候选顺序、Combo 策略、协议转换、失败阶段均可查看。
6. **本机安全默认**：只监听回环地址，密钥不进入 EXE、日志或文档。
7. **单次完整交付**：除辅助调用链的详细分步成本归集明确延期外，其余本文范围全部完成。

## 3. 最终菜单

1. 仪表盘
2. 供应商
3. 上游模型
4. 统一模型
5. 辅助模型
6. API Token
7. 路由状态
8. 调用日志
9. 价格与用量
10. 预算控制
11. Agent 配置
12. 系统设置

## 4. 核心业务对象

### 4.1 供应商模板

内置只读模板，至少包含：名称、协议族、默认 Base URL、认证方式、模型列表路径、能力、默认请求头、文档地址和验证状态。

模板分为：

- 专用适配：OpenAI、Anthropic、Gemini、SenseNova 等已经有独立适配器的供应商。
- 兼容适配：使用 OpenAI-Compatible、Anthropic Messages 或 Gemini 兼容协议。
- 未验证模板：提供经过官方文档核对的默认信息，但明确标记“未验证”。
- 本地服务：Ollama、LM Studio、vLLM、LocalAI、llama.cpp。

模板目录至少覆盖现有目录，并扩充 Cerebras、SambaNova、NVIDIA NIM、Perplexity、Cloudflare Workers AI/AI Gateway、Hugging Face Inference Providers、GitHub Models、DeepInfra、Replicate、Fal AI、Novita、Featherless AI、Nscale、OVHcloud AI Endpoints、Scaleway 和 WaveSpeedAI。

本轮不实现在线模板更新；模板随软件版本发布。

新增模板的默认协议和地址必须以官方文档为依据，当前调研入口：

- [NVIDIA NIM API](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html)
- [Cloudflare Workers AI OpenAI 兼容接口](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/)
- [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/en/index)
- [Cerebras Inference](https://inference-docs.cerebras.ai/api-reference/authentication)
- [SambaNova API](https://docs.sambanova.ai/docs/en/api-reference/overview)
- [Perplexity OpenAI Compatibility](https://docs.perplexity.ai/docs/agent-api/openai-compatibility)
- [GitHub Models Catalog](https://docs.github.com/en/rest/models/catalog)
- [DeepInfra](https://docs.deepinfra.com/)
- [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility)
- [LM Studio API](https://lmstudio.ai/docs/developer/rest)

### 4.2 供应商实例

用户从模板或手动创建入口生成。每个实例包含：

- 实例名称
- 模板类型或自定义类型
- 上游协议族
- Base URL
- 加密 API Key
- 加密 OAuth/附加凭据（适用时）
- 自定义请求头
- 超时、代理、启用状态
- 连接测试结果和最后测试时间

同一模板可以创建任意多个实例。实例直接显示在供应商列表，不再建立账号或节点子层级。

### 4.3 上游模型

必须属于一个供应商实例。通过远端模型接口同步或手工添加，支持编辑：

- 上游模型 ID 和显示名
- 输入/输出能力
- 上下文长度
- 输入、输出、缓存价格
- 标签
- 本地启用状态
- 远端可用状态
- 最后同步时间

重新同步时新增远端模型并更新已有元数据；远端消失但已被引用的模型标记为“远端不可用”，不自动删除。

### 4.4 统一模型

统一模型是客户端请求中的稳定模型名。一个统一模型可以绑定多个上游模型，并为每个候选配置优先级、权重、启用状态和能力覆盖。

支持路由模式 `static`、`combo`、`auto`，Combo 策略沿用并完善：

- `priority`
- `weighted`
- `round_robin`
- `least_used`
- `cost_optimized`
- `quota_headroom`
- `last_known_good`

统一模型可以同时开启多个对外协议；协议开启不代表能力自动存在，仍需能力校验。

### 4.5 辅助模型

从“供应商 → 上游模型”选择后配置为辅助模型。同一上游模型可以同时是主候选和辅助模型。

三种模式：

1. 关闭。
2. 每个统一模型单独配置。
3. 全局辅助模型池，默认模式。

辅助工作流可独立启用和排序，包括视觉转文本、文件提取/摘要、上下文压缩、工具调用规划、音频转写、结构化输出修复和其他可组合能力。失败时立即返回明确阶段错误，不使用未配置模型。

### 4.6 API Token

API Token 是客户端访问 APISwitch 的凭据，与供应商 API Key 完全分离。支持名称、权限范围、有效期、启停、最后使用时间和预算归属。明文只在创建时返回一次。

## 5. 对外协议范围

全部经过统一模型路由：

- OpenAI Chat Completions
- OpenAI Responses
- Anthropic Messages
- Gemini v1beta
- Embeddings
- Files
- Images
- Audio
- Moderations
- Rerank
- Search
- Batches
- WebSocket
- Video
- Music

文本、流式、工具、图片、文件、音频、Embedding 和媒体能力都进入统一协议内核。无法可靠转换时返回结构化“不兼容”错误，由用户手动选择正确模型。

## 6. Agent 配置

首期完整支持 Claude Code，分别选择主模型、Opus、Sonnet、Haiku，统一使用当前网关地址。支持预览、路径检查、备份、原子写入、恢复和一键覆盖。

保留 Codex、Gemini CLI、OpenCode 等后续扩展入口。端口变化后自动更新所有已启用 Agent 配置，并在覆盖前备份。

## 7. 系统与发布

- Windows 单文件 `APISwitch.exe`。
- 数据目录 `%USERPROFILE%\.apiswitch`。
- 单实例；重复启动只唤醒已有窗口。
- 最小化或关闭进入托盘；托盘支持显示、隐藏、自启动和退出。
- 优先监听 `127.0.0.1:8080`；占用时自动选择端口。
- 当前地址写入运行状态并供前端、Agent 配置读取。
- 系统设置包含端口、目录、自启动、上传限制、备份恢复、密钥、系统信息和 WebDAV。

## 8. WebDAV

同步范围为全部用户数据：数据库、供应商密钥、Token、模型、路由、日志、文件、设置和主密钥。使用独立备份密码整体加密，任何敏感信息不得明文上传。

必须支持：连接测试、加密导出、差异预览、上传、下载、恢复前本地备份、冲突处理和同步日志。

## 9. 数据重置决策

新版不迁移旧业务数据。首次启动新版数据库结构时：

1. 备份旧数据库。
2. 创建全新数据库。
3. 不导入旧供应商、模型、Token 和日志。
4. 初始化默认系统设置，辅助模式默认为全局池。

## 10. 明确延期

辅助调用链本批只记录基础成功/失败和失败阶段。每一步的独立 Token、成本、延迟和预算归集放到下一批，其他需求不得以此为由延期。
