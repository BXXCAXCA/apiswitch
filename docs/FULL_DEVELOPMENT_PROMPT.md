# 全流程开发任务提示词

将下面完整内容复制到一个新的 Codex 任务中即可开始全流程开发。

```text
你正在 E:\apiswitch 仓库中继续开发 APISwitch。请把本任务作为一次持续到真正完成的全流程重构任务，不要只给建议或方案，要直接修改代码、测试、构建并验证 Windows 单文件 EXE。

开始前必须完整阅读：
- README.md
- docs/README.md
- docs/01-product-requirements.md
- docs/02-information-architecture.md
- docs/03-system-architecture.md
- docs/04-data-model.md
- docs/05-protocol-routing.md
- docs/06-desktop-security-backup.md
- docs/07-development-and-acceptance.md
- docs/08-api-contracts.md

以上文档是唯一需求和设计基线。现有代码只是可复用素材；如果与文档冲突，以文档为准。不要恢复旧的 Provider Connection/Provider Node 页面或层级。

总目标：完成新版 APISwitch 的全部重构并交付 Windows 单文件 dist\APISwitch.exe。除“辅助调用链每一步的独立 Token、成本、延迟和预算归集”明确延期外，文档中的其他功能必须全部完成。本任务不得在只完成某个阶段时宣称完成。

必须实现：
1. 最终 12 个菜单：仪表盘、供应商、上游模型、统一模型、辅助模型、API Token、路由状态、调用日志、价格与用量、预算控制、Agent 配置、系统设置。
2. 供应商采用模板目录 + 独立实例。同一模板可添加多个不同 API Key，显示为多个供应商实例；手动供应商可选择 OpenAI-Compatible、Anthropic Messages、Gemini 或自定义协议并配置 Base URL、密钥和自定义头。
3. 删除新业务路径中的 Connection/Node 层级。上游模型直接属于供应商实例，可远端拉取或手工添加；同步时保留被引用但远端消失的模型并标记不可用。
4. 统一模型直接绑定上游模型，支持多个候选、优先级、权重、启停、原有全部 Combo 策略，以及同时开启多个对外协议。
5. 建立统一 Canonical Request/Response/Event 协议内核。OpenAI Chat、Responses、Anthropic Messages、Gemini v1beta、Embeddings、Files、Images、Audio、Moderations、Rerank、Search、Batches、WebSocket、Video、Music 全部经过同一统一模型、能力、路由、日志和错误管线。
6. 协议无法可靠转换或能力不兼容时返回明确结构化错误，不静默丢字段，不自动换其他统一模型。
7. 辅助模型支持 disabled、per-unified-model、global-pool 三模式，默认 global-pool。按“供应商 → 上游模型 → 辅助能力/工作流”配置；同一模型可同时作为主候选和辅助模型。实现视觉转文本、文件提取、上下文压缩、工具规划、音频转写、结构化修复和终端能力等可排序工作流。步骤失败立即返回失败阶段，不调用未配置模型。本批只需基础辅助链日志，不做延期的分步成本归集。
8. 路由状态同时显示协议映射矩阵、Combo 候选与原因、健康/熔断/额度，以及协议转换 dry-run 测试台；展示入口、Canonical、上游请求、上游响应和最终响应。
9. API Token 放在辅助模型之后，始终保护网关端点。供应商 API Key 与客户端 Token 严格区分。
10. Claude Code 配置分别选择主模型、Opus、Sonnet、Haiku，支持预览、备份、原子写入和恢复。Base URL 使用当前网关地址；端口变化自动备份并更新所有已启用配置。保留 Codex、Gemini CLI、OpenCode 扩展入口。
11. 系统设置整合运行、端口、数据目录、开机自启动、上传限制、数据库备份恢复、密钥、系统信息和 WebDAV。WebDAV 使用独立备份密码，对数据库、API Key、Token、日志、文件、设置和主密钥进行全量加密归档；错误密码或损坏不得修改本地数据。
12. Windows 桌面端数据目录为 %USERPROFILE%\.apiswitch。优先监听 127.0.0.1:8080，占用时自动换端口并写 runtime.json。实现当前用户单实例，重复启动唤醒窗口；保留托盘、后台启动、自启动和优雅退出。
13. 新版数据库不迁移旧业务数据。检测旧 schema 时先使用安全方式备份旧数据库，再创建全新数据库。失败必须回滚或阻止启动，不能产生半初始化状态。
14. 供应商模板覆盖文档列出的全部供应商；未完成专用适配或未经真实调用验证的模板必须标记“兼容模式/未验证”，不能假装已完整适配。
15. 不使用真实供应商作为本轮验收条件。使用 Mock、模拟 HTTP 上游和固定协议样例。不要读取、复用、打印或写入聊天历史中曾出现的测试密钥，任何真实密钥都不得进入代码、测试、文档、日志或 EXE。

执行方式：
- 先检查 git status 和现有测试，不覆盖用户无关改动。
- 建立可持续更新的实施计划，但不要因为任务大而停在计划阶段。
- 按 docs/07-development-and-acceptance.md 的 A-I 阶段连续实施；每阶段完成相关代码、迁移、UI 和自动化测试后继续下一阶段。
- 优先复用可验证的现有实现；对于与新结构冲突的旧代码，安全移除或重写。
- 所有文件修改使用适当的补丁方式；不要执行 git reset --hard、checkout -- 或其他破坏用户改动的操作。
- 如果遇到普通实现选择，依据文档作合理决定并继续，不要反复要求用户确认。
- 只有遇到会实质改变产品范围、造成数据/外部系统不可逆影响且文档没有答案的事项才暂停提问。
- 在长时间工作中持续提供简短进度更新，直到全部完成或出现真实外部阻塞。

质量要求：
- 为新数据库、供应商实例、模型同步、Combo、全部协议、辅助工作流、WebDAV、Agent、单实例和动态端口编写测试。
- 后端测试必须全部通过：python -m pytest backend\tests -q。
- 前端测试必须全部通过：npm run test。
- TypeScript 和生产构建必须通过：npm run build。
- 执行 git diff --check。
- 执行 .\scripts\package-desktop.ps1 -Clean。
- 真实运行 dist\APISwitch.exe，验证健康接口、前端资源、%USERPROFILE%\.apiswitch、托盘、单实例、后台模式和端口冲突处理。
- 构建时清除可能把开发机 VITE_* 密钥编入前端的环境变量，并对产物执行敏感信息检查。

完成条件：
- docs/07-development-and-acceptance.md 中的完成定义全部满足。
- 不得以“代码框架已建立”“基础功能已完成”“后续可继续”等理由提前结束。
- 最终回复用中文，说明实际完成范围、测试结果、EXE 绝对路径、文件大小、SHA-256、数据目录和仅剩的已确认延期项。
```
