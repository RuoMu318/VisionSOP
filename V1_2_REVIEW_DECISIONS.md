# V1.2 架构评审决策记录

| 评审主题 | 决策 | 落位 |
| --- | --- | --- |
| 状态、结果与处置混用 | 采纳。拆分 `cycle_state`、`conformance_result` 与 `disposition`；`FAIL_HOLD` 仅为 UI 派生名称，人工放行不能改写不合规事实。 | 实施方案 5.2、5.5、7.2-7.5 |
| HARD Evidence 可靠性 | 采纳。增加 Cycle Binding、Freshness、Validity、source sequence 和 Evidence quality；HARD 不再被描述为绝对真理。 | 5.3 |
| 证据冲突策略 | 采纳。SOP Schema 增加 missing/conflict/timeout policy；冲突与缺证据进入 `ON_HOLD`，使用 `REVIEW_HOLD` 等原因码。 | 5.3 |
| ENFORCING 的实际执行 | 采纳。定义 PLC Quality Handshake、序号 ACK 和质量放行条件；没有可控质量放行点时，模式最高为 ADVISORY。 | 5.7、6.5、9、12 |
| PostgreSQL 故障与追溯 | 采纳。关键 Event 先写本地 fsync WAL；PostgreSQL 不可持续写入时进入 `ON_HOLD`，禁止 `RESULT_VALID`，恢复后回放。 | 5、5.5、10、12 |
| Event 演进与完整运行条件 | 采纳。增加 `schema_version`、`runtime_bundle_id`，并引入不可变 Runtime Configuration Bundle；Cycle 开始时冻结。 | 5.3、5.4、5.5 |
| 时间准确度 | 采纳。保留毫秒字段但新增跨服务时钟偏差 SLA 与 `CLOCK_UNSYNCED` 处理，不把格式精度当作实际准确度。 | 5.3、8.2 |
| WebRTC 工程设计 | 采纳。冻结为 DeepStream/GStreamer `webrtcbin` Gateway、API 信令、WSS、短时令牌、LAN 2-5 Viewer 与 M1 POC。 | 5.8 |
| 相机位置完整性 | 采纳。Camera Profile 加入 ArUco/治具特征对齐基线，偏差产生 `CAMERA_CALIBRATION_INVALID` 并按依赖 ON_HOLD。 | 5.1、8.1、12 |
| 模型漂移 | 采纳。增加 Model Health 指标、验收基线、滚动窗口与 `MODEL_DRIFT_WARNING`，不自动重训练。 | 6.3 |
| 统计验收样本量 | 采纳。训练采集目标与 Production Acceptance Run 分离；以零误报支持 1/200 的 95% 上界需至少 600 个独立正常 Cycle。 | 3、6.4、9 |
| 网络、账号和接口安全 | 采纳。冻结 TLS/WSS、会话、RBAC、CSRF/CORS、Rate Limit、Secret、最小权限、防火墙及授权处置审计。 | 8.2、10 |
| 数据库恢复与审计 | 采纳。增加版本化迁移、Backup Restore Drill、append-only 审计与应用角色不可删改约束。 | 8.2、9、10、12 |
| 系统报警与工艺 NG | 采纳。定义 `PROCESS_ALARM` 与 `SYSTEM_ALARM` Domain；系统故障不计入不良率。 | 7.2、12 |
| 排期前提 | 采纳。14-16 周明确依赖 2-4 名可并行核心开发人员与现场支持，单人实施须重新估算。 | 1 |

## 未采纳项

无。所有建议均在单工位 V1 的生产可追溯、质量裁决和现场运行边界内，不需要扩展为多工位平台或安全控制系统。
