# 数据模型

## 1. 重建策略

新版使用新的 schema generation。检测到旧库时：

1. 关闭后台调度和写入。
2. 使用 SQLite Backup API 创建时间戳备份。
3. 将旧库重命名为只读历史备份。
4. 创建全新数据库和表。
5. 写入 schema generation 和默认系统设置。

不迁移旧业务数据。失败时保留旧库并终止启动，不允许半初始化。

## 2. 核心表

### `schema_metadata`

- `generation`
- `app_version`
- `created_at`
- `reset_from_backup`

### `provider_instances`

- `id`
- `name`（唯一）
- `template_key`
- `protocol_type`
- `base_url`
- `api_key_encrypted`
- `oauth_encrypted_json`
- `custom_headers_encrypted_json`
- `timeout_seconds`
- `proxy_type` / `proxy_url_encrypted`
- `enabled`
- `verification_status`
- `last_tested_at` / `last_test_error`
- timestamps

不建立 Provider Connection 或 Provider Node 外键。

### `upstream_models`

- `id`
- `provider_instance_id`
- `model_id`
- `display_name`
- `input_capabilities_json`
- `output_capabilities_json`
- `context_window`
- `max_output_tokens`
- `input_price` / `output_price` / `cached_input_price`
- `currency` / `pricing_source` / `pricing_effective_at`
- `tags_json`
- `enabled`
- `remote_status`：`available`、`missing`、`unknown`
- `remote_metadata_json`
- `last_synced_at`
- timestamps

唯一约束：`provider_instance_id + model_id`。

### `unified_models`

- `id`
- `name`（客户端稳定模型名，唯一）
- `description`
- `required_capabilities_json`
- `enabled_protocols_json`
- `routing_mode`
- `combo_strategy`
- `preferred_tier`
- `session_affinity_enabled`
- `max_cost_per_request` / `max_latency_ms` / `min_context_window`
- `enabled`
- timestamps

### `unified_model_candidates`

- `id`
- `unified_model_id`
- `upstream_model_id`
- `priority`
- `weight`
- `capability_overrides_json`
- `enabled`
- timestamps

唯一约束：`unified_model_id + upstream_model_id`。

### `auxiliary_settings`

单例设置：

- `mode`：`disabled`、`per_unified_model`、`global_pool`
- `updated_at`

默认 `global_pool`。

### `auxiliary_models`

- `id`
- `upstream_model_id`
- `unified_model_id`（全局池为空）
- `capabilities_json`
- `priority`
- `enabled`
- timestamps

### `auxiliary_workflows`

- `id`
- `scope` / `unified_model_id`
- `workflow_type`
- `input_capability`
- `output_capability`
- `ordered_steps_json`
- `enabled`
- timestamps

### `api_tokens`

- 名称、前缀、哈希、scopes、有效期、启用状态、最后使用时间和 timestamps。
- 永不保存明文 Token。

### `request_logs`

- 请求 ID、时间、入口协议、统一模型
- 最终供应商实例、上游模型
- Combo 策略和候选摘要
- 基础辅助链摘要和失败阶段
- Token、成本、延迟、首 Token 延迟
- 成功、错误类型、脱敏错误消息
- API Token ID

### `provider_health` / `circuit_breakers`

健康和熔断绑定 `upstream_model_id`，必要时聚合到供应商实例。保留 closed/open/half-open 状态机。

### `usage_history` / `quota_snapshots` / `budgets`

用量可按 API Token、统一模型、供应商实例和上游模型聚合。预算 scope 支持 global、token、unified_model、provider_instance。

### `stored_files` / `batch_jobs`

保留文件和批处理持久化，但所有模型引用改为统一模型名称/ID。

### `agent_configs`

- `agent_type`
- `profile_name`
- `config_path`
- `enabled`
- `main_model_id`
- `opus_model_id` / `sonnet_model_id` / `haiku_model_id`
- `last_written_base_url`
- `last_backup_path`
- timestamps

### `system_settings`

保存非敏感设置；敏感设置使用单独加密字段。至少包括首选端口、上传限制、辅助模式、备份策略和当前模板版本。

### `webdav_profiles` / `webdav_sync_logs`

WebDAV 密码和备份密码只保存加密值。同步日志保存方向、远端版本、校验值、冲突决定和结果，不保存密码。

## 3. 引用与删除规则

- 被统一模型候选引用的上游模型不能删除。
- 被辅助模型引用的上游模型不能删除。
- 含上游模型的供应商实例不能直接删除，必须先解除引用或显式级联确认。
- 含调用记录的 API Token 可以删除管理对象，但日志保留可空外键和前缀快照。
- 删除操作统一返回 `409 resource_in_use` 和引用摘要。

## 4. 密钥规则

- API Key、OAuth、代理密码、自定义敏感头、WebDAV 密码均加密。
- Token 只保存强哈希。
- 主密钥不进入 SQLite；桌面端保存在 `%USERPROFILE%\.apiswitch` 的受控文件中。
- WebDAV 归档使用与本地主密钥不同的备份密钥派生方案。
