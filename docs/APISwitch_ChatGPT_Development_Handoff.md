# APISwitch ChatGPT 开发交接文档

> 用途：将本文件或同名 DOCX 上传到 ChatGPT Chat 模式，使新的对话可以快速恢复项目背景、当前完成度、验证证据和后续开发约束。
>
> 生成日期：2026-07-23（Asia/Shanghai）  
> GitHub：`https://github.com/BXXCAXCA/apiswitch`  
> 当前分支：`agent/complete-protocol-support`  
> 功能基线提交：`a0ab13062f8cac31f9dfca12d011ff610d880b0d`  
> Draft PR：`https://github.com/BXXCAXCA/apiswitch/pull/1`

## 1. 如何在 ChatGPT Chat 模式继续

1. 上传本 Markdown 或 `APISwitch_ChatGPT_Development_Handoff.docx`。
2. 同时提供 GitHub 仓库链接；如果仓库不可公开读取，请再上传最新源码压缩包。
3. 将第 12 节的“可直接复制提示词”作为新对话的第一条开发指令。
4. 让 ChatGPT 先检查实际分支、提交和工作区，不要只依据本文猜测代码状态。
5. 涉及真实供应商时，使用你现场提供的新测试凭据；不要把密钥写入代码、日志、文档或构建产物。

## 2. 项目定位

APISwitch 是 Windows 优先、本地优先的多供应商 AI API 网关。客户端只使用稳定的“统一模型”名称，网关内部负责：

- 供应商模板与多个独立供应商实例；
- 上游模型发现、维护和能力声明；
- 统一模型及 Combo 候选路由；
- OpenAI、Anthropic、Gemini 与终端任务协议转换；
- 辅助模型工作流；
- 客户端 Token、预算、用量和调用日志；
- Agent 配置、WebDAV 加密备份；
- Windows 单实例、托盘、动态端口和单文件发布。

最终业务路径是：

```text
供应商模板 → 供应商实例 → 上游模型
→ 统一模型/辅助模型 → 客户端 API Token → 统一网关调用
```

旧的 Provider Connection / Provider Node 层级不得重新引入。

## 3. 当前架构与技术栈

```text
Windows Desktop Host
├─ Single Instance / IPC / Tray / Auto-start
├─ Port Manager（优先 127.0.0.1:8080，冲突时换端口）
└─ FastAPI + Vue
   ├─ Admin API
   ├─ Gateway API
   ├─ Canonical Protocol Engine
   ├─ Provider Adapters
   ├─ Unified Model Router
   ├─ Auxiliary Workflow Engine
   ├─ Accounting / Budget / Logs
   └─ Agent / Backup / WebDAV
```

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11、FastAPI、SQLAlchemy、Alembic、SQLite |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Naive UI |
| 桌面端 | pywebview、Windows 系统托盘、PyInstaller 单文件 |
| 数据目录 | `%USERPROFILE%\.apiswitch` |
| 默认网关 | `http://127.0.0.1:8080`，端口冲突时自动选择可用端口 |

请求主链路：

```text
Token 验证
→ 入口协议解析
→ Canonical Request
→ 能力校验与辅助工作流
→ Combo 候选路由
→ 上游协议转换与调用
→ Canonical Response/Event
→ 入口协议响应
→ 日志、用量、预算和健康状态
```

## 4. 当前产品完成度

当前实现已经完成新版业务结构和 12 个管理页面：

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

已覆盖的核心能力包括：

- 版本化供应商模板、同模板多实例、手动供应商、自定义头、代理和加密凭据；
- 上游模型远端同步、手动维护、幂等合并、远端消失标记和引用保护；
- 统一模型直接绑定 `upstream_model_id`，支持多候选与全部 Combo 策略；
- `priority`、`weighted`、`round_robin`、`least_used`、`cost_optimized`、`quota_headroom`、`last_known_good`；
- disabled、per-unified-model、global-pool 三种辅助模式及所有文档化工作流；
- Token 单次明文展示、哈希存储、scope、模型授权、过期、轮换和隔离；
- 请求预算、价格、用量、日志、熔断、健康、失败切换和会话粘性；
- Claude Code 四模型映射以及 Codex、Gemini CLI、OpenCode 等 Agent 配置入口；
- 数据库旧 schema 备份重建、WebDAV 全量加密备份与安全恢复；
- Windows 单实例、唤醒、托盘、自启动、后台模式、动态端口和单文件 EXE。

## 5. 协议覆盖与验证边界

下表表示代码路径和自动化契约已经通过 Mock、模拟 HTTP 上游与固定协议样例验证。它不等同于每一家真实云供应商均已使用真实密钥完成兼容认证。

| 协议/能力 | 对外入口 | 当前自动化验证 |
|---|---|---|
| OpenAI Chat | `POST /v1/chat/completions` | Canonical、工具、SSE、候选失败切换、HTTP 上游 |
| OpenAI Responses | `POST /v1/responses` | Canonical、字段校验、流式事件、不可转换项拒绝 |
| Anthropic Messages | `POST /v1/messages` | 原生入口/上游转换、工具、流式词汇、参数保留 |
| Gemini v1beta | `generateContent`、`streamGenerateContent` | 原生 HTTP、`generationConfig`、JSON Schema、单 candidate 约束 |
| Embeddings | `POST /v1/embeddings` | Token 保护、统一模型、终端协议 HTTP 路径 |
| Files | `/v1/files` | 上传、列表、元数据、内容、删除、Token 隔离、批处理引用保护 |
| Images | generations、edits、variations | 生成路径及 edits/variations 原生 multipart 转发 |
| Audio | speech、transcriptions | 二进制语音透传、Content-Type、转写 multipart |
| Moderations | `POST /v1/moderations` | 统一管线与实际上游路径 |
| Rerank | `POST /v1/rerank` | 统一管线与实际上游路径 |
| Search | `POST /v1/search` | 统一管线与实际上游路径 |
| Batches | `/v1/batches` | 文件校验、Token 隔离、引用生命周期 |
| WebSocket | `/v1/ws/chat/completions` | Canonical 流事件、工具增量、Token 保护 |
| Video | `/v1/videos/generations` 及状态查询 | 终端协议 HTTP 路径与结构化响应 |
| Music | `/v1/music/generations` 及状态查询 | 终端协议 HTTP 路径与结构化响应 |

最近一次协议完善重点：

- 修正图片编辑、图片变体和音频转写的真实上游路径；
- 对 multipart 文件和字段执行原生转发；
- 语音生成支持二进制响应和上游 `Content-Type` 透传；
- 补全 Files 的完整本地生命周期和 Token 隔离；
- Gemini 保留采样、停止、最大输出和 JSON Schema 参数；
- Gemini `candidateCount > 1` 无法无损表示时返回 `protocol_conversion_unsupported`；
- 增加原生 Anthropic、Gemini 和终端协议 HTTP 传输测试；
- 统一 UTC 时间生成，消除项目自身的 naive datetime 警告。

## 6. 最新验证证据

2026-07-23 在 `agent/complete-protocol-support` 分支重新执行：

| 验证项 | 结果 |
|---|---|
| 后端 | `110 passed, 1 warning in 59.97s` |
| 前端 | `4 test files / 23 tests passed` |
| TypeScript + Vite 生产构建 | 通过 |
| Ruff 关键错误检查 | `All checks passed!`（`F,E9`） |
| `git diff --check` | 通过 |
| PyInstaller Windows 单文件构建 | 已通过 |
| EXE 冒烟测试 | 健康接口、前端资源和本地运行已通过 |

唯一 pytest 警告来自第三方 FastAPI/Starlette TestClient 对 `httpx` 的弃用提示，不是项目运行错误。

Vite 构建仍提示主 JS chunk 大于 500 kB：当前压缩前约 963.75 kB、gzip 后约 263.67 kB。构建成功，但后续可通过路由懒加载或代码拆分优化首屏资源。

Windows 发布产物：

| 字段 | 值 |
|---|---|
| 路径 | `E:\apiswitch\dist\APISwitch.exe` |
| 大小 | 37,772,095 bytes（约 36.02 MiB） |
| SHA-256 | `C2B3BAAE61FEA59CDEDEDB1C89AEB5044E41FD62B95680399F168652FDB59059` |
| 用户数据目录 | `%USERPROFILE%\.apiswitch` |

## 7. GitHub 状态

- 仓库：`https://github.com/BXXCAXCA/apiswitch`
- 分支：`agent/complete-protocol-support`
- 功能基线提交：`a0ab130` — `complete protocol support and validation`
- Draft PR：`https://github.com/BXXCAXCA/apiswitch/pull/1`
- PR 基线：`main`
- GitHub 当前未返回 CI status checks；本地验证结果见第 6 节。

继续开发前先运行：

```powershell
git status -sb
git log -1 --oneline
git fetch origin
git diff origin/main...HEAD --stat
```

不要用 `git reset --hard`、`git checkout -- <file>` 等方式覆盖未知的用户改动。

## 8. 关键文件地图

| 位置 | 作用 |
|---|---|
| `README.md` | 项目入口、产品状态、技术栈和开发命令 |
| `docs/01-product-requirements.md` | 产品目标和范围 |
| `docs/03-system-architecture.md` | 模块边界、请求生命周期和错误原则 |
| `docs/04-data-model.md` | 新版数据库实体与引用关系 |
| `docs/05-protocol-routing.md` | Canonical、协议矩阵、Combo、流式和辅助工作流 |
| `docs/06-desktop-security-backup.md` | Windows、密钥、安全、WebDAV 与恢复 |
| `docs/07-development-and-acceptance.md` | A-I 阶段、测试矩阵和完成定义 |
| `docs/08-api-contracts.md` | Admin/Gateway 稳定契约 |
| `backend/apiswitch/gateway/v2.py` | 网关入口、Files 和 multipart/binary 处理 |
| `backend/apiswitch/protocols/canonical.py` | Canonical 请求/响应/事件 |
| `backend/apiswitch/routing/engine.py` | 候选过滤与 Combo 排序 |
| `backend/apiswitch/routing/executor.py` | 上游请求构造、HTTP 调用和响应归一化 |
| `backend/apiswitch/api/admin/v2.py` | 新版管理 API |
| `backend/apiswitch/db/` | 模型、初始化和 schema generation |
| `backend/tests/v2_test_*.py` | 后端 110 项自动化测试 |
| `frontend/src/views/` | 12 个产品页面 |
| `frontend/tests/` | 23 项 UI、路由与日期测试 |
| `scripts/package-desktop.ps1` | Windows 单文件打包 |
| `APISwitch.spec` | PyInstaller 配置 |

## 9. 必须保持的实现约束

- 所有模型字段都指向统一模型，不允许客户端直接选择供应商或上游模型。
- 所有网关端点都必须经过 Token、能力、辅助、路由、日志和错误管线。
- 转换不能静默丢失会改变语义的字段；不支持时返回结构化错误。
- 不得自动改用未配置的统一模型或未配置的辅助模型。
- 供应商 API Key 与客户端 Token 必须严格分离。
- API Key、Token、备份密码、主密钥和完整敏感响应不得进入日志、测试、文档或 EXE。
- 完整 Prompt/Response 默认不持久化。
- 新版数据库不迁移旧业务数据；旧 schema 必须先安全备份，再全量重建。
- Files 必须保持 Token 隔离，并保护被 Batch 引用的文件。
- Agent 写入必须遵循“预览 → 备份 → 临时文件 → 原子替换”。
- WebDAV 恢复必须先验证密码、版本和校验值，失败不得修改本地数据。
- 真实云服务未经真实调用验证时继续标记“兼容模式/未验证”。

## 10. 已知限制和诚实边界

### 唯一确认延期项

辅助调用链每一步的独立 Token、成本、延迟和预算归集。现有实现已经保留基础辅助链日志、失败阶段和总请求统计。

### 非阻塞技术债

- 未使用真实云供应商密钥逐家认证；当前验收基于 Mock、模拟 HTTP 上游和固定样例。
- Vite 主 chunk 超过默认 500 kB 警告阈值，可后续进行视图懒加载和依赖拆分。
- FastAPI/Starlette TestClient 有 1 条第三方弃用警告，可在依赖升级时处理。
- Draft PR 尚无 GitHub CI checks；若准备合并，建议增加 Windows CI、测试和打包产物校验。

## 11. 推荐的下一阶段工作

建议按以下顺序继续：

1. 在不提交密钥的前提下，建立真实供应商可选认证套件和结果登记表。
2. 为每个协议增加脱敏 golden fixtures，固定请求/响应/错误兼容性。
3. 增加 GitHub Actions：后端、前端、Windows PyInstaller、敏感信息扫描和产物哈希。
4. 将前端 12 个视图改为路由懒加载，拆分 Naive UI 和大依赖 chunk。
5. 实现唯一延期项：辅助链逐步骤 Token、成本、延迟和预算归集。
6. 准备正式 Release：版本号、变更日志、签名、安装/升级和回滚说明。

每项完成后都应重新执行全量测试、生产构建、单文件打包和真实 EXE 冒烟测试。

## 12. 可直接复制到 ChatGPT 的继续开发提示词

```text
你正在继续开发 APISwitch。请先完整阅读我上传的
“APISwitch ChatGPT 开发交接文档”，然后读取 GitHub 仓库：
https://github.com/BXXCAXCA/apiswitch

目标分支为 agent/complete-protocol-support，功能基线提交为
a0ab13062f8cac31f9dfca12d011ff610d880b0d，Draft PR 为：
https://github.com/BXXCAXCA/apiswitch/pull/1

如果你无法直接读取仓库，请明确告诉我需要上传哪些源码文件或压缩包；
不要根据交接文档虚构尚未看到的代码。

接手后必须先做：
1. 检查实际 git status、当前分支、HEAD 和远端差异，保护已有用户改动。
2. 完整阅读 README.md 和 docs/01 至 docs/08。
3. 核对交接文档中的测试数量、协议矩阵、EXE 信息和当前实现是否仍一致。
4. 建立本轮任务计划，然后直接修改、测试和验证；不要只给建议。

架构与产品约束：
- 保持“供应商实例 → 上游模型 → 统一模型/辅助模型”的新版结构。
- 不得恢复 Connection/Node 业务层级。
- 所有协议必须使用 Canonical 管线、统一模型、能力校验、Combo 路由、
  Token、预算、日志和结构化错误。
- 不静默丢字段，不自动切换到未配置统一模型，不调用未配置辅助模型。
- 供应商 API Key 与客户端 Token 严格分离。
- 真实供应商未经真实调用验证时必须标记兼容模式/未验证。
- 不读取、复用、打印或提交任何真实密钥。

当前自动化基线：
- 后端 110 passed；
- 前端 23 passed；
- TypeScript/Vite build 通过；
- Ruff F,E9 通过；
- Windows 单文件构建与冒烟测试通过。

当前唯一确认延期项是：
“辅助调用链每一步的独立 Token、成本、延迟和预算归集”。
不要把其他缺失功能擅自归类为延期。

若我没有另行指定新功能，请先执行一次差距审计，重点检查：
- 文档与实现是否一致；
- 全部协议的真实 HTTP 路径、multipart、binary、SSE、WebSocket 和错误转换；
- 安全、Token 隔离、预算、熔断、WebDAV 恢复和 Agent 原子写入；
- GitHub CI、前端 chunk 拆分和正式 Release 准备。

完成任何改动后至少执行：
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run test
npm run build
cd ..
backend\.venv\Scripts\python.exe -m ruff check backend --select F,E9
git diff --check
.\scripts\package-desktop.ps1 -Clean

涉及桌面或发布时还要实际运行 dist\APISwitch.exe，验证健康接口、前端资源、
用户数据目录、端口冲突、单实例和安全退出，并重新计算大小与 SHA-256。

最终用中文说明：实际改动、测试结果、剩余限制、分支/提交/PR，以及可复现命令。
```

## 13. 常用命令

```powershell
# 后端
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe -m ruff check backend --select F,E9

# 前端
cd frontend
npm run test
npm run build
cd ..

# 差异与格式
git status -sb
git diff --check

# Windows 单文件
.\scripts\package-desktop.ps1 -Clean

# 产物哈希
Get-FileHash -Algorithm SHA256 .\dist\APISwitch.exe
```

---

本交接文档是开发上下文快照。继续开发时，以实际仓库、当前分支、测试输出和 `docs/` 下的产品文档为最终依据。
