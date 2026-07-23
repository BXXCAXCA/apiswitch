# APISwitch

APISwitch 是一个 Windows 优先、本地优先的多供应商 AI API 网关。客户端只使用稳定的“统一模型”名称，软件在内部完成供应商实例管理、上游模型同步、协议转换、Combo 路由、辅助模型工作流、鉴权、预算、日志和 Agent 配置。

> 文档与实现基线：2026-07-16。新版业务路径已经切换到“供应商实例 → 上游模型 → 统一模型/辅助模型”，不再暴露 Connection/Node 页面或接口依赖。

## 当前实现状态

- 十二个管理页面、Canonical 协议内核、全部确认网关入口、Combo 路由、三种辅助模式、Token、日志、价格、预算、Agent 和 WebDAV 已接入新版数据结构。
- Windows 桌面端使用 `%USERPROFILE%\.apiswitch`，支持单实例唤醒、托盘、后台启动、自启动、8080 冲突换端口和安全退出。
- 供应商模板中的真实云服务均明确标记为“未验证”或“兼容模式”；自动化验收只使用 Mock、模拟 HTTP 上游和固定协议样例。
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

- [文档索引](docs/README.md)
- [产品需求](docs/01-product-requirements.md)
- [界面与使用流程](docs/02-information-architecture.md)
- [系统架构](docs/03-system-architecture.md)
- [数据模型](docs/04-data-model.md)
- [协议、路由与辅助模型](docs/05-protocol-routing.md)
- [桌面运行、安全与备份](docs/06-desktop-security-backup.md)
- [开发计划与验收](docs/07-development-and-acceptance.md)
- [API 契约](docs/08-api-contracts.md)
- [全流程开发任务提示词](docs/FULL_DEVELOPMENT_PROMPT.md)
- [ChatGPT 开发交接文档](docs/APISwitch_ChatGPT_Development_Handoff.md)

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
npm install
npm run test
npm run build

# Windows 单文件桌面端
cd ..
.\scripts\package-desktop.ps1 -Clean
```

发布产物为 `dist\APISwitch.exe`。真实供应商密钥不得进入代码、测试、日志、文档或构建产物。
