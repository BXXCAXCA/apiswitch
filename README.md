# APISwitch

APISwitch 是一个 Windows 优先、本地优先的多供应商 AI API 网关。客户端只使用稳定的“统一模型”名称，软件在内部完成供应商实例管理、上游模型同步、协议转换、Combo 路由、辅助模型工作流、鉴权、预算、日志和 Agent 配置。

> 文档与实现基线：2026-08-05。新版业务路径已经切换到“供应商实例 → 上游模型 → 统一模型/辅助模型”，不再暴露 Connection/Node 页面或接口依赖。

## 当前实现状态

- 十二个管理页面、Canonical 协议内核、全部确认网关入口、Combo 路由、三种辅助模式、Token、日志、价格、预算、Agent 和 WebDAV 已接入新版数据结构。
- Windows 桌面端使用 `%USERPROFILE%\.apiswitch`，支持单实例唤醒、托盘、后台启动、自启动、8080 冲突换端口和安全退出。
- 供应商模板中的真实云服务均明确标记为“未验证”或“兼容模式”；自动化验收只使用 Mock、模拟 HTTP 上游和固定协议样例。
- 前端十二个管理视图按路由懒加载，Vite 将 Vue、Naive UI、KaTeX、图标和其他依赖拆分为独立 chunk。
- GitHub Actions 自动执行 Windows 后端测试与 Ruff、Ubuntu 前端测试与生产构建，以及 Windows PyInstaller 单文件打包、SHA-256 记录、产物上传和 GitHub Release 发布。
- 当前发布版本为 [`v0.1.7`](https://github.com/BXXCAXCA/apiswitch/releases/tag/v0.1.7)：将 OpenAI Responses 流式完成事件压缩为跨 AI SDK 版本兼容的最小终止帧，追加标准 `[DONE]`，并在响应头暴露 APISwitch 版本与 SSE 兼容模式，修复正文已返回但 Cherry Studio 仍报告 `finish reason "other"` 的问题。
- 唯一确认延期项是“辅助调用链每一步的独立 Token、成本、延迟和预算归集”；基础辅助链日志、失败阶段和总请求统计已经实现。

## 最终产品流程

```text
供应商模板 → 添加供应商实例 → 拉取/维护上游模型
→ 创建统一模型并绑定候选 → 配置辅助模型工作流
→ 创建客户端 API Token → 通过统一网关协议调用
```

## 最终菜单

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

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、Alembic、SQLite
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Naive UI
- 桌面端：pywebview、Windows 系统托盘、PyInstaller 单文件发布
- 数据目录：`%USERPROFILE%\.apiswitch`
- 默认网关：优先 `http://127.0.0.1:8080`，冲突时自动换端口

## 文档入口

- **在 GPT 网页版继续开发**：先使用 [续开发交接包](docs/CONTINUE_IN_GPT.md)。
- 详细设计与 API 契约：见 [文档索引](docs/README.md)。
- 当前发布与安装包：见 [GitHub Releases](https://github.com/BXXCAXCA/apiswitch/releases)。

## 开发命令

```powershell
# 后端
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r ..\requirements.txt -r ..\requirements-dev.txt
pytest

# 前端
cd ..\frontend
npm ci
npm run test
npm run build

# Windows 单文件桌面端
cd ..
.\scripts\package-desktop.ps1 -Clean
```

发布产物为 `dist\APISwitch-v<版本号>.exe`。真实供应商密钥不得进入代码、测试、日志、文档或构建产物。
