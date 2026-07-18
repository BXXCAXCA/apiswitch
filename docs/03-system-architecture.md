# 系统架构

## 1. 架构目标

采用模块化单体：一个 FastAPI 后端、一个 Vue 管理界面、一个 SQLite 数据库和一个 Windows 桌面宿主。协议、供应商、路由、辅助工作流、备份和 Agent 写入保持独立模块边界。

```text
Windows Desktop Host
├─ Single Instance / IPC
├─ Port Manager
├─ Tray / Auto-start
└─ FastAPI + Vue UI
   ├─ Admin API
   ├─ Gateway API
   ├─ Provider Adapters
   ├─ Canonical Protocol Engine
   ├─ Unified Model Router
   ├─ Auxiliary Workflow Engine
   ├─ Accounting / Budget / Logs
   └─ Agent / Backup / WebDAV
```

## 2. 模块边界

### 2.1 Desktop Host

负责数据目录、单实例锁、已有实例唤醒、首选端口探测、托盘、自启动、后端线程、窗口生命周期和运行状态文件。不得包含业务路由逻辑。

### 2.2 Provider Catalog

代码内置版本化模板。模板是只读数据，不保存用户密钥。每个模板声明协议、默认地址、认证方式、模型发现能力、能力范围、官方文档和验证状态。

### 2.3 Provider Instance Service

管理用户实际添加的供应商实例。负责加密凭据、连接测试、代理、自定义请求头和实例级健康信息。旧的 Connection/Node 服务从新业务路径移除。

### 2.4 Upstream Model Service

通过供应商适配器拉取模型、合并本地覆盖、维护远端状态和引用完整性。同步算法必须幂等。

### 2.5 Canonical Protocol Engine

每个入口协议先转换为统一内部对象，再按选中的供应商协议转换为上游请求。响应走相反方向。转换器不得直接查询数据库或决定路由。

内部对象至少覆盖：

- 文本和多段内容
- 系统、用户、助手、工具角色
- 工具定义、调用和结果
- 图片、文件、音频引用
- 流式事件
- Embedding、图片、音频、媒体任务
- Token/usage 和结构化错误

### 2.6 Unified Model Router

输入统一模型、能力要求、协议要求和请求约束，输出排序后的上游模型候选。处理 Combo、健康、熔断、价格、额度、预算和会话粘性。

### 2.7 Auxiliary Workflow Engine

在路由前计算能力缺口，按模式匹配辅助模型和工作流。每一步都有明确输入、输出和失败阶段。它只能使用显式配置的辅助模型。

### 2.8 Accounting and Audit

请求级记录最终统一模型、供应商实例、上游模型、协议、候选链、基础辅助链、Token、成本、延迟、预算结果和错误。完整 Prompt/Response 默认不持久化。

### 2.9 Agent Service

根据当前运行地址和统一模型生成 Agent 配置。写入必须采用“预览 → 备份 → 临时文件 → 原子替换”，端口变化时只更新已启用配置。

### 2.10 Backup Service

创建一致性 SQLite 快照，收集文件和密钥，使用独立备份密码加密为单一归档，再交给 WebDAV 客户端传输。恢复先验证归档、版本、校验值和密码。

## 3. 请求生命周期

```text
1. 客户端 Token 验证
2. 解析入口协议
3. 转换为 Canonical Request
4. 加载统一模型及入口协议配置
5. 校验请求能力
6. 规划辅助工作流
7. 执行可组合的辅助步骤
8. Combo 选择主上游模型
9. 转换为供应商协议并调用
10. 转换响应或流式事件
11. 写入日志、用量、预算和健康状态
```

步骤 3、5、6、8、9、10 的错误必须携带 `stage`，前端能直接显示失败环节。

## 4. 单实例与端口

- 使用当前 Windows 用户范围的命名互斥体或等效锁。
- 首实例启动本地 IPC 唤醒通道。
- 后续启动只发送“显示窗口”指令并退出。
- 端口按首选值 8080 开始探测；被占用时选择可用端口。
- 写入 `%USERPROFILE%\.apiswitch\runtime.json`，包含 PID、端口、Base URL、版本和启动时间。
- 端口变化后触发 Agent 配置更新和备份。

## 5. 错误原则

统一错误结构：

```json
{
  "error": {
    "type": "capability_not_supported",
    "message": "The selected unified model cannot satisfy audio transcription",
    "stage": "capability_check",
    "request_id": "req_...",
    "details": {}
  }
}
```

禁止：伪造成功、静默丢字段、自动改用未配置统一模型、在错误中回显密钥或完整敏感上游响应。

## 6. 代码组织目标

```text
backend/apiswitch/
├─ api/admin/
├─ api/gateway/
├─ catalog/
├─ providers/
├─ protocols/
├─ routing/
├─ auxiliary/
├─ accounting/
├─ agents/
├─ backup/
├─ desktop/
└─ db/
```

可以渐进移动现有文件，但最终接口不得依赖旧 Connection/Node 层级。
