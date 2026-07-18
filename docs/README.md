# APISwitch 新版文档索引

本目录是 2026-07-16 确认的唯一需求和设计基线。旧的 OmniRoute 路线、Connection/Node 层级、旧菜单和旧里程碑文档已经废弃。

## 阅读顺序

1. [产品需求](01-product-requirements.md)：产品边界、菜单、核心对象与完成范围。
2. [界面与使用流程](02-information-architecture.md)：十二个页面的职责和用户操作路径。
3. [系统架构](03-system-architecture.md)：模块边界、运行时流程和错误原则。
4. [数据模型](04-data-model.md)：全新数据库结构和旧库覆盖策略。
5. [协议、路由与辅助模型](05-protocol-routing.md)：统一协议内核、Combo 和辅助调用链。
6. [桌面运行、安全与备份](06-desktop-security-backup.md)：单实例、托盘、端口、密钥和 WebDAV。
7. [开发计划与验收](07-development-and-acceptance.md)：全量交付顺序、质量门槛和完成定义。
8. [API 契约](08-api-contracts.md)：目标管理 API、网关 API 和结构化错误。
9. [全流程开发任务提示词](FULL_DEVELOPMENT_PROMPT.md)：在新 Codex 任务中直接使用的完整指令。

## 决策优先级

发生冲突时按以下顺序处理：

1. 用户后续明确提出的新要求。
2. `01-product-requirements.md`。
3. 其余专项设计文档。
4. 现有代码行为。

现有代码仅作为可复用实现素材，不得反向覆盖已确认的新产品逻辑。
