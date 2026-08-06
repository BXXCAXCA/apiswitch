# 在 GPT 网页版继续开发 APISwitch

> 本文是当前唯一的续开发交接入口。更新时间：2026-08-06（Asia/Shanghai）。
>
> 仓库：[BXXCAXCA/apiswitch](https://github.com/BXXCAXCA/apiswitch) · 默认分支：`main` · 当前发布：[v0.1.12](https://github.com/BXXCAXCA/apiswitch/releases/tag/v0.1.12)

## 使用方法

1. 在新的 GPT 网页版对话中上传本文；同时提供仓库链接。若 GPT 无法读取仓库，再上传当前源码压缩包，而不是旧的 DOCX 交接文件。
2. 将下面的“可复制提示词”作为第一条开发指令，并在后续消息中说明本轮要实现的具体目标。
3. 让助手先读取实际仓库状态；本文是导航与验证快照，不能取代代码。

## 当前可靠状态

- 产品主链路固定为：`供应商实例 → 上游模型 → 统一模型/辅助模型 → 客户端 API Token → 统一网关调用`。不得恢复旧的 Connection/Node 结构。
- OpenAI Chat、Responses、Anthropic、Gemini 及文件、图像、音频等入口都应经过 Canonical 管线、能力检查、路由、Token、日志与结构化错误处理。
- `v0.1.12` 在视觉能力声明修复基础上，支持收集并无损聚合 OpenAI-Compatible 上游 SSE。零输出 `choices: null` 会有限退避并切换为流式上游，正文、思考、工具调用分片和 Token 用量均进入 Canonical 响应。
- Windows 桌面端已修复陈旧运行时状态阻塞启动的问题；默认网关优先使用 `127.0.0.1:8080`，端口冲突时自动回退。
- GitHub Actions 会在 `main` 推送后运行后端、前端、敏感信息扫描、Windows 打包和冒烟测试；全部成功后自动创建/更新同版本 GitHub Release，并上传 EXE 与 SHA-256。

## 最近验证结果

| 项目 | 结果 |
|---|---|
| 后端测试 | `134 passed` |
| 前端测试 | `25 passed` |
| Ruff | `backend` 的 `F,E9` 检查通过 |
| 本地 Windows 打包 | `dist/APISwitch-v0.1.12.exe` 已生成并通过桌面冒烟测试 |
| 云端 CI 与发布 | `main` 推送后由 GitHub Actions 自动构建并发布 [v0.1.12](https://github.com/BXXCAXCA/apiswitch/releases/tag/v0.1.12) |

真实上游供应商仍可能返回额度或速率限制（例如 HTTP 429）；这属于供应商账户/配额状态，不应与协议转换错误混淆。

## 阅读顺序

1. [根 README](../README.md)：产品概览、开发命令与发布入口。
2. [产品需求](01-product-requirements.md)：范围与不可改变的产品决策。
3. [系统架构](03-system-architecture.md) 与 [协议、路由和辅助模型](05-protocol-routing.md)：改网关、SSE、路由或协议时必读。
4. [数据模型](04-data-model.md)、[API 契约](08-api-contracts.md)：改数据库或 HTTP 接口时必读。
5. [桌面、安全与备份](06-desktop-security-backup.md)、[开发计划与验收](07-development-and-acceptance.md)：改桌面端、配置或发布时必读。

## 关键文件地图

| 路径 | 职责 |
|---|---|
| `backend/apiswitch/gateway/v2.py` | 网关入口、Responses SSE、二进制与 multipart 路径 |
| `backend/apiswitch/protocols/canonical.py` | Canonical 请求、响应与事件模型 |
| `backend/apiswitch/routing/` | 统一模型候选、路由排序与上游执行 |
| `backend/tests/v2_test_*.py` | 网关与协议自动化测试 |
| `frontend/src/` | Vue 管理界面 |
| `scripts/package-desktop.ps1` | Windows 单文件打包 |
| `scripts/verify-desktop-package.ps1` | 已打包 EXE 的健康、端口与单实例冒烟测试 |
| `.github/workflows/ci.yml` | CI、Windows 打包、Release 自动发布 |

## 不可违反的约束

- 不读取、打印、提交或复用任何真实 API Key、Token、备份密码或完整敏感响应。
- 客户端只能选择统一模型；不得让客户端直连供应商实例或上游模型。
- 不静默丢弃会改变语义的协议字段；无法无损转换时返回结构化错误。
- 不自动切换到未配置的统一模型或辅助模型。
- Files、Token、日志与预算必须保持租户/Token 隔离。
- 修改前保护已有工作区改动；不要使用 `git reset --hard` 或 `git checkout -- <file>` 覆盖未知内容。

## 每次改动后的验证

```powershell
# 后端
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe -m ruff check backend --select F,E9

# 前端
Push-Location frontend
npm run test
npm run build
Pop-Location

# 格式、打包与桌面冒烟
git diff --check
.\scripts\package-desktop.ps1 -Clean
.\scripts\verify-desktop-package.ps1
```

涉及真实上游时，先用脱敏 Mock 或你现场提供的临时凭据复现；HTTP 429 需要检查对应供应商的账户额度、速率限制和并发策略。

## 可直接复制给 GPT 的提示词

```text
你正在继续开发 APISwitch。请先读取我上传的 CONTINUE_IN_GPT.md，
再读取仓库 https://github.com/BXXCAXCA/apiswitch 的 main 分支。

先执行并汇报：git status -sb、git log -1 --oneline、当前版本、
与本文声明是否一致。不要假设旧的 ChatGPT 交接文档、DOCX、分支或
测试数量仍然正确。

随后阅读 README.md、docs/01-product-requirements.md、
docs/03-system-architecture.md 和 docs/05-protocol-routing.md；如果本轮涉及
数据库、API、桌面或发布，再读取对应专项文档。

严格保持：供应商实例 → 上游模型 → 统一模型/辅助模型的结构；所有网关调用
必须经过 Canonical、鉴权、能力检查、路由、日志和结构化错误管线。不得泄露
或提交密钥，不得静默丢失语义字段，不得覆盖我已有的工作区改动。

我的本轮目标是：<在此填写具体需求>。

完成后必须运行与改动匹配的后端测试、前端测试/构建、Ruff、git diff --check；
涉及桌面端时再运行 package-desktop.ps1 和 verify-desktop-package.ps1。
请用中文交付：实际改动、验证结果、剩余限制、当前提交及可复现命令。
```
