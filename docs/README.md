# APISwitch 文档索引

本目录包含两类资料：`01` 至 `08` 是产品与实现的设计基线；续开发文档记录当前仓库、版本与验证状态。旧的 OmniRoute 路线、Connection/Node 层级、旧菜单和旧里程碑文档已经废弃。

## 在 GPT 网页版继续开发

先阅读并上传 [CONTINUE_IN_GPT.md](CONTINUE_IN_GPT.md)。它是唯一面向 GPT 网页版的当前交接入口，包含当前版本、已验证结果、关键近期修复、阅读顺序、验证命令及可直接复制的提示词。

## 阅读顺序

1. [产品需求](01-product-requirements.md)：产品边界、菜单、核心对象与完成范围。
2. [界面与使用流程](02-information-architecture.md)：十个主导航页面及高级设置的职责和用户操作路径。
3. [系统架构](03-system-architecture.md)：模块边界、运行时流程和错误原则。
4. [数据模型](04-data-model.md)：全新数据库结构和旧库覆盖策略。
5. [协议、路由与辅助模型](05-protocol-routing.md)：统一协议内核、Combo 和辅助调用链。
6. [桌面运行、安全与备份](06-desktop-security-backup.md)：单实例、托盘、端口、密钥和 WebDAV。
7. [开发计划与验收](07-development-and-acceptance.md)：全量交付顺序、质量门槛和完成定义。
8. [API 契约](08-api-contracts.md)：目标管理 API、网关 API 和结构化错误。
9. [续开发交接包](CONTINUE_IN_GPT.md)：GPT 网页版与其他开发助手的当前入口。
10. [历史资料归档](archive/README.md)：旧提示词和阶段性交接材料，仅供追溯。
11. [全流程开发任务提示词（历史）](archive/FULL_DEVELOPMENT_PROMPT.md)。
12. [ChatGPT 开发交接文档（历史）](archive/APISwitch_ChatGPT_Development_Handoff.md) 与 [DOCX 副本](archive/APISwitch_ChatGPT_Development_Handoff.docx)。

## 决策优先级

发生冲突时按以下顺序处理：

1. 用户后续明确提出的新要求。
2. `01-product-requirements.md`。
3. 其余专项设计文档。
4. 现有代码行为。

现有代码仅作为可复用实现素材，不得反向覆盖已确认的新产品逻辑。
