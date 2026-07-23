# API 契约

本文定义目标接口分组和稳定语义。开发时可细化字段，但不能恢复旧的 Connection/Node 业务层级。

## 1. 系统

- `GET /health`
- `GET /api/admin/runtime`
- `GET /api/admin/diagnostics`
- `GET/PATCH /api/admin/settings`
- `GET/PATCH /api/admin/settings/startup`
- `POST /api/admin/database/backup`
- `POST /api/admin/database/restore`

`runtime` 返回当前 Base URL、端口、数据目录、版本、schema generation、单实例和桌面状态，不返回密钥。

## 2. 供应商模板和实例

- `GET /api/admin/provider-templates`
- `GET /api/admin/provider-instances`
- `POST /api/admin/provider-instances`
- `GET/PATCH/DELETE /api/admin/provider-instances/{id}`
- `POST /api/admin/provider-instances/{id}/test`
- `POST /api/admin/provider-instances/{id}/duplicate`

模板只读；实例写接口接受凭据，读接口只返回 `credential_configured`。

## 3. 上游模型

- `GET /api/admin/provider-instances/{id}/upstream-models`
- `POST /api/admin/provider-instances/{id}/upstream-models/sync`
- `POST /api/admin/provider-instances/{id}/upstream-models`
- `PATCH/DELETE /api/admin/upstream-models/{id}`
- `POST /api/admin/upstream-models/bulk`

同步返回 added、updated、marked_missing、unchanged 和 errors。

## 4. 统一模型

- `GET/POST /api/admin/unified-models`
- `GET/PATCH/DELETE /api/admin/unified-models/{id}`
- `POST /api/admin/unified-models/{id}/candidates`
- `PATCH/DELETE /api/admin/unified-models/{id}/candidates/{candidate_id}`
- `GET /api/admin/unified-models/{id}/protocol-matrix`

候选请求只引用 `upstream_model_id`，不得再要求 Provider/Connection/Node 组合字段。

## 5. 辅助模型

- `GET/PATCH /api/admin/auxiliary/settings`
- `GET/POST /api/admin/auxiliary/models`
- `PATCH/DELETE /api/admin/auxiliary/models/{id}`
- `GET/POST /api/admin/auxiliary/workflows`
- `PATCH/DELETE /api/admin/auxiliary/workflows/{id}`
- `POST /api/admin/auxiliary/plan`

`plan` 为 dry-run，返回能力差距、选中步骤、模型和失败原因。

## 6. Token、路由、日志、用量和预算

- `/api/admin/tokens`
- `/api/admin/router/status`
- `POST /api/admin/router/convert/test`
- `/api/admin/logs`
- `/api/admin/accounting/pricing`
- `/api/admin/accounting/usage`
- `/api/admin/budgets`

转换测试默认使用 Mock，不得无提示调用真实供应商。

## 7. Agent

- `GET /api/admin/agents`
- `POST /api/admin/agents/claude-code/preview`
- `POST /api/admin/agents/claude-code/write`
- `POST /api/admin/agents/claude-code/restore`
- `POST /api/admin/agents/refresh-base-url`

Claude Code 请求包含 main、opus、sonnet、haiku 四个统一模型 ID。写入前必须预览并备份。

## 8. WebDAV

- `GET/POST/PATCH/DELETE /api/admin/webdav/profiles`
- `POST /api/admin/webdav/profiles/{id}/test`
- `GET /api/admin/webdav/profiles/{id}/archives`
- `POST /api/admin/webdav/export`
- `POST /api/admin/webdav/preview`
- `POST /api/admin/webdav/upload`
- `POST /api/admin/webdav/download`
- `POST /api/admin/webdav/restore`
- `GET /api/admin/webdav/logs`

备份密码仅写入；接口响应不得包含密码、派生密钥或主密钥。

## 9. 网关

网关端点范围见 `05-protocol-routing.md`。所有网关请求：

- `GET /v1/models` 使用 OpenAI 模型目录结构返回当前可调用的统一模型，不暴露上游模型或供应商凭据。
- 使用统一模型名称。
- 要求 `Authorization: Bearer <APISWITCH_TOKEN>`。
- 产生统一请求 ID。
- 经过能力、辅助链、Combo、预算和日志管线。

Files 接口提供当前 Token 隔离的完整本地文件生命周期：

- `POST /v1/files` 上传 multipart 文件。
- `GET /v1/files` 只列出当前 Token 的文件。
- `GET /v1/files/{id}` 返回当前 Token 的文件元数据。
- `GET /v1/files/{id}/content` 下载原始内容或批处理 JSONL 输出。
- `DELETE /v1/files/{id}` 删除未被批处理引用的文件；被引用时返回 `resource_in_use`。

`/v1/images/edits`、`/v1/images/variations` 和 `/v1/audio/transcriptions` 接受并向 OpenAI-Compatible 上游原样转发原生 multipart 字段和文件。`/v1/audio/speech` 支持透传上游二进制音频及其 Content-Type。Gemini `generationConfig` 的采样、停止、最大输出和 JSON Schema 参数进入 Canonical 管线；无法无损表示的多 candidate 请求明确返回 `protocol_conversion_unsupported`。

## 10. 错误

统一外层结构：

```json
{
  "error": {
    "type": "resource_in_use",
    "message": "Upstream model is referenced by a unified model",
    "stage": "validation",
    "request_id": "req_123",
    "details": {
      "references": []
    }
  }
}
```

标准类型至少包括：

- `validation_error`
- `authentication_error`
- `resource_in_use`
- `provider_unavailable`
- `model_remote_missing`
- `protocol_not_enabled`
- `protocol_conversion_unsupported`
- `capability_not_supported`
- `auxiliary_workflow_not_configured`
- `auxiliary_step_failed`
- `budget_exceeded`
- `webdav_backup_invalid`
- `database_generation_mismatch`

HTTP 状态和入口协议错误格式可适配，但日志中的内部类型必须稳定。
