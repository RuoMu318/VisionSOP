# V1.4 完整落地方案：摄像头单设备、可扩展的单工位 SOP 合规平台

> 本版将“AI 给证据，确定性系统做裁决；证据不足时 HOLD，绝不猜 PASS/FAIL”定义为 V1 的强制架构原则。

> 历次独立评审的采纳结果与具体落位见 [V1_1_REVIEW_DECISIONS.md](V1_1_REVIEW_DECISIONS.md) 与 [V1_2_REVIEW_DECISIONS.md](V1_2_REVIEW_DECISIONS.md)。

> V1.4 将交付分为 P0 Software Foundation 与 M0-M6 Camera Field Integration。P0 可在没有相机或现场数据时完成；当前现场 V1 只接入一台固定工业相机。PLC、扫码枪、电批和传感器的 Adapter Contract 保留为后续扩展，但不绑定当前 Runtime Bundle，也不作为当前验收前提。

> 当前代码状态必须如实区分：P0 已实现并在本机验证 USB OpenCV 的实时取帧、JPEG 快照、MJPEG 预览和相机健康状态，但视觉 Evidence 仍只有 `simulated-vision`，尚无真实检测算法。接入摄像头本身只能获得视频，完成模型接入并通过 Shadow 验收后才能输出视觉检测结果。Windows OpenCV 仅用于开发接入；正式 Ubuntu/NVIDIA 部署仍采用 DeepStream/TensorRT。

## 1. 交付决策

V1 是一个可在真实产线运行的单工位试点，不是多工位平台或动作识别演示。系统在工厂局域网 Edge Industrial PC 上完成采集、判断、留证和展示，在网络与云端不可用时仍可继续运行。

**上线闭环**：

```text
固定工业相机
        -> 目标 / 状态 / 动作视觉证据
        -> SOP 确定性判定
        -> 视觉合规结果 + 生命周期状态 + 授权处置
        -> 异常前后视频、事件、截图
        -> Web 监控与 SN 质量追溯
```

P0 不依赖现场硬件或真实数据，可立即启动；M0-M6 仅在相机、目标工位和工艺输入到位后启动。原 14 至 16 周现场接入排期以 2 至 4 名可并行的核心开发人员（CV、Edge/后端、前端）及工艺、质量现场支持为前提；若由单人覆盖 AI、DeepStream、后端和前端，排期需重新估算。

## 2. V1 范围与边界

### 2.1 纳入范围

- 单一装配/检测工位，固定治具、固定相机、单人操作。
- 5 至 8 个顺序明确的 SOP 步骤。
- 一个产品型号，或外观、步骤和关键零件一致的产品族。
- 目标/状态检测与少量关键动作识别，所有 Required Evidence 必须来自摄像头可观察事实。
- 当前步骤、进度、漏步、错序、超时、质量合规结果、生命周期状态、授权处置、报警和证据留存。
- 工位详情、异常中心、SN 追溯、受控的相机/SOP 配置页面。
- 在 P0 使用模拟 Camera/Model Adapter 完成全流程演示与自动化测试。

### 2.2 不纳入范围

- 自动理解任意 SOP 文档、零训练跨工位部署、复杂多人协作。
- 非线性分支工艺、复杂返工流程和未知异常的在线判定。
- MES 全量双向流程集成，仅保留 V1 REST/事件接口。
- AI 参与安全急停、安全门、安全光栅或任何机器安全控制。
- STORM-PSR、StateDiffNet、AMNAR、Task Graph 作为生产判定依赖。
- PLC、扫码枪、电批、传感器和 MES 的真实接入；接口保留到后续版本。
- 对真实扭矩、设备 ACK、内部不可见装配状态或安全联锁作出视觉结论。

### 2.3 阶段边界

| 阶段 | 当前可执行内容 | 明确不允许的动作 |
| --- | --- | --- |
| `P0 Software Foundation` | UI、API、SOP Engine、数据库、WAL、Evidence 抽象、Adapter Contract、模拟相机与模拟视觉模型、Shadow/Advisory 演示。 | 宣称真实识别准确率、伪造硬件证据、输出质量互锁或进入 ENFORCING。 |
| `M0-M6 Camera Field Integration` | 站点配置、真实 Camera/Model Adapter、DeepStream/TensorRT、模型训练、Benchmark、Shadow、视觉验收。 | 跳过 M0 输入冻结、统计验收或稳定性测试；把视觉动作解释为真实扭矩/设备结果。 |

## 3. 成功标准

| 项目 | V1 验收目标 |
| --- | --- |
| 实时性 | 普通违规从事件产生到 Web 告警小于 2 秒。 |
| 视频 | 稳定实时预览；相机掉线自动重连；掉线只显示 `CAMERA_OFFLINE`，不判 SOP NG。 |
| 步骤模型 | 普通步骤 F1 >= 90%；关键步骤同时评估 Precision 与 Recall，阈值按工艺风险在 M0 冻结。 |
| 错误放行 | 整周期 False PASS Rate / Escape Rate、关键违规 Recall、Missed NG Rate 必须独立统计；不得仅用 Precision 代替。数值由质量风险分级和冻结验收集确定。 |
| 错误拦截 | 整周期 False FAIL Rate 单独统计，作为人工处置负担和产线体验指标。 |
| 规则 | 对正确的 Step Event 输入，漏步、错序、超时和依赖判断为 100% 确定性正确。 |
| 统计验收 | 开发样本与生产验收样本分离；若以零误报支持误报率低于 1 / 200 的 95% 上界，至少需要 600 个独立正常 Cycle。关键违规 Recall 的样本量按风险和目标置信度单独计算。 |
| 追溯 | 每个 NG 均有违规原因、来源证据、截图、事件 JSON 和前后视频。 |
| 可用性 | 服务重启后自动恢复；相机或模型不可用状态可见且可审计。关键质量 Event 的 RPO 目标为 0（写入本地持久化日志后才可裁决）；RTO 在 M0/M1 按工位节拍冻结。 |

### 3.1 P0 软件基础验收

- 在无真实硬件环境下，通过模拟 Adapter 驱动完整 `ARMED -> RUNNING -> CLOSED`、`ON_HOLD`、`AWAITING_DISPOSITION` 和 `ABORTED` 流程。
- 同一份 SOP、Cycle、Evidence、Runtime Bundle、报警、审计和 SN 追溯逻辑同时适用于模拟与真实 Adapter。
- UI 能显示模拟实时状态、模拟视频、证据、PROCESS/SYSTEM Alarm、质量处置和历史回放。
- 替换 `simulated` Camera/Model Adapter 为真实实现只能改变站点配置与适配器实现，不得修改 SOP Engine、事件合同、数据库 Schema 或前端业务流程。
- P0 仅运行 `SIMULATION`、`SHADOW` 或 `ADVISORY`；`ENFORCING` 被硬性禁用。

## 4. 使用的 GitHub 仓库

V1 只将下列仓库引入实际工作链路或研发流程。完整清单与后续阶段边界见 [GITHUB_REPOSITORIES.md](GITHUB_REPOSITORIES.md)。

| 领域 | 仓库 | V1 使用方式 | 是否进入在线判定链路 |
| --- | --- | --- | --- |
| 视频运行时 | [NVIDIA DeepStream](https://github.com/NVIDIA/DeepStream) | 正式视频底座：RTSP/USB、GPU 解码、TensorRT、Tracking、ROI、多流预留。 | 是 |
| DeepStream 示例 | [DeepStream Python Apps](https://github.com/NVIDIA-AI-IOT/deepstream_python_apps) | 只参考 RTSP、元数据与推理示例；禁止作为 V1 主工程模板。正式代码使用 DeepStream 9.1 + Service Maker，不以已弃用 `pyds` 形成核心代码。 | 否，参考 |
| 训练基础 | [PyTorch](https://github.com/pytorch/pytorch) | 模型训练、离线评测、ONNX 导出。 | 间接 |
| 目标/状态模型 | [Ultralytics](https://github.com/ultralytics/ultralytics) | 训练工件、手、工具、零件、治具和关键装配状态模型；仅在 M0 许可证决策通过后采用。 | 是，导出 TensorRT 后 |
| 动作模型 | [MMAction2](https://github.com/open-mmlab/mmaction2) | 训练、验证、Fine-tuning 与 ONNX 导出；生产推理由 DeepStream Sequence Preprocess + TensorRT `nvinfer` 执行。 | 是，同一 GPU Pipeline |
| 数据设计 | [IndustReal](https://github.com/TimSchoonbeek/IndustReal) | 参考步骤、状态、错误样本和标注方法。 | 否，研发参考 |
| 数据参考 | [HA-ViD](https://github.com/iai-hrc/ha-vid)、[InHARD](https://github.com/vhavard/InHARD) | 用于预训练可行性、标注规范和实验设计。 | 否，研发参考 |

以下仓库明确不阻塞 V1 上线：[STORM-PSR](https://github.com/shaohsuanhung/STORM-PSR)、[StateDiffNet](https://github.com/Dan-Leh/find-my-assembly-mistakes)、[AMNAR](https://github.com/iSEE-Laboratory/AMNAR)、[Differentiable Task Graph Learning](https://github.com/fpv-iplab/Differentiable-Task-Graph-Learning)、PREGO、GTG2Vid、MS-TCN2、ASFormer 与 Assembly101。它们在 V3/V4 或离线实验阶段评估，不能替代 V1 的确定性规则。

**M0.1 许可决策门**：在任何数据训练前，项目必须书面选择以下之一：购买 Ultralytics Enterprise License；或替换为经许可证审查通过的训练实现，例如 [MMDetection](https://github.com/open-mmlab/mmdetection) + RTMDet。未经决策，不得将 Ultralytics 代码、权重或训练产物纳入闭源商业交付。

在引入任何仓库、权重或数据集前，记录 commit/release、许可证、模型权重许可、数据集条款、依赖 CVE 与责任人。版本锁定文件必须记录 DeepStream、CUDA、TensorRT、GPU 驱动、PyTorch、模型、ONNX、TensorRT Engine 和 SOP 版本。

## 5. 技术架构

```text
Camera -> Video Runtime / DeepStream -> TensorRT Vision Models
                                           |
                                           v
                                  Versioned Vision Evidence
                                           |
                                           v
Event Ingress -> Local Durable Journal -> SOP Engine -> PostgreSQL
                                              |             |
                                              v             v
                                      Evidence Service   API / WebSocket
                                                            |
                                                            v
                                                          Web UI

Future Device Adapters (disabled in current V1) -> Event Ingress

Evidence Service: DeepStream Smart Recording -> raw.mp4, snapshot.jpg, event.json
```

### 5.1 服务边界

| 服务 | 责任 | V1 失败处理 |
| --- | --- | --- |
| `video-runtime` | 相机连接、解码、帧率、循环缓冲、ROI、曝光和场景完整性健康状态 | 断线重连；发布 `CAMERA_OFFLINE` 或 `CAMERA_CALIBRATION_INVALID`，不生成工艺失败。 |
| `ai-runtime` | DeepStream GPU Pipeline 内的 TensorRT 目标/状态/动作推理、追踪、时序过滤和推理指标 | 发布 `AI_UNAVAILABLE`；拒绝产生伪造步骤完成事件。 |
| `device-io` | 仅保留后续扩展边界，当前 V1 不部署、不绑定 Runtime Bundle | 后续启用时仍须输出标准 Event，禁止直接修改 Cycle。 |
| `event-journal` | 本地 append-only WAL、fsync、顺序恢复与 PostgreSQL 回放 | 关键 Event 无法 fsync 时发布 `SYSTEM_ALARM` 并使活跃 Cycle 进入 `ON_HOLD`；不产生可放行结果。 |
| `sop-engine` | Cycle、步骤状态、依赖、超时、合规结果、处置与 Runtime Bundle 冻结 | 单一状态写入者；规则与证据版本可追溯。 |
| `evidence-service` | 基于 DeepStream Smart Recording 的环形缓存、异常截取、截图与文件索引 | 默认保存原始 MP4、截图和事件 JSON；叠加视频按需生成或在浏览器回放时叠加 Event。 |
| `api-server` | REST、WebSocket、WebRTC 信令、权限、查询与审计 | 不承担视频或模型推理。 |
| `web-ui` | 现场状态、质量处置、追溯和配置 | Web 断开不影响 Edge 判定。 |

建议使用 Docker Compose 管理上述服务与 PostgreSQL。`event-journal` 是 V1 必需的本地持久化模块，不以 Redis 替代。Redis Streams 如需引入，仅用于进程解耦和消费分发，不作为关键质量 Event 的唯一持久化来源。

### 5.2 Cycle 生命周期与处置

Cycle 由 SOP Engine 单一管理。为防止质量事实被人工处置覆盖，存储模型严格拆分为生命周期、合规结果和处置三类字段：

| 概念 | 字段 | 允许值 | 用途 |
| --- | --- | --- | --- |
| 生命周期 | `cycle_state` | `IDLE`、`ARMED`、`RUNNING`、`ON_HOLD`、`AWAITING_DISPOSITION`、`CLOSED` | 当前流程能否继续及其所处阶段。 |
| SOP 合规结果 | `conformance_result` | `UNKNOWN`、`CONFORMING`、`NONCONFORMING`、`ABORTED` | 工艺事实；一旦 `NONCONFORMING`，不能被人工改写为 `CONFORMING`。 |
| 质量处置 | `disposition` | `NONE`、`REWORK`、`SCRAP`、`AUTHORIZED_RELEASE` | 对 NG 产品的授权后续动作。 |

`FAIL_HOLD` 仅是 UI 对 `AWAITING_DISPOSITION + NONCONFORMING` 的显示名称；`HOLD` 仅是 UI 对 `ON_HOLD` 的显示名称，不再作为顶层结果字段。

```text
IDLE
  -> ARMED          SN 已绑定，等待产品就绪
  -> RUNNING        产品就绪，开始接受步骤证据
      -> ON_HOLD                 必需证据、数据库或系统不可用；结果仍为 UNKNOWN
      -> AWAITING_DISPOSITION    发生确定性违规；结果为 NONCONFORMING
      -> CLOSED                  全部条件满足且 CycleEnd；结果为 CONFORMING
      -> CLOSED                  取消/复位/换型；结果为 ABORTED
ON_HOLD
  -> RUNNING        恢复后重新验证所有未完成条件
  -> AWAITING_DISPOSITION / CLOSED  按后续证据或取消事件裁决
AWAITING_DISPOSITION
  -> CLOSED         SCRAP 或 AUTHORIZED_RELEASE
  -> RUNNING        REWORK 产生新的 rework attempt；原 NONCONFORMING 事实保留
```

Camera-only V1 的 Cycle Start 默认契约为 `product_code_readable + product_in_fixture`；Cycle End 为“所有 Required Step 完成并观察到 `product_removed`”。如果产品码无法在画面中可靠读取，M0 必须选择人工录入或外部系统提供 SN，此时该输入只用于 Cycle 绑定，不得伪装成视觉识别结果。

必须覆盖：重复识别产品码、识别不同 SN、中途取走产品、相机重连、软件重启、Cycle 取消、NG 产品取走、重新开始与产品型号切换。重启后 SOP Engine 以事件日志和最新持久化 checkpoint 重放未关闭 Cycle；无法安全恢复时进入 `ON_HOLD`，由授权人员处置。

`AWAITING_DISPOSITION` 的最小处置流程为：质量或班组授权人员选择 `REWORK`、`SCRAP` 或 `AUTHORIZED_RELEASE`；每项操作写入用户、时间、客户端、原因、旧结果、新结果和关联证据。`AUTHORIZED_RELEASE` 不删除原 `NONCONFORMING` 事实，只追加审核决策；`REWORK` 也必须保留原始违规和重工尝试链。

### 5.3 事件、时间与判定原则

所有输入统一为不可变 Event；AI、设备和 UI 均无权直接修改步骤状态。SOP Engine 依据 Event、SOP Version 和 Cycle Context 唯一决定结果。

```json
{
  "event_id": "uuid",
  "schema_version": "1.2",
  "runtime_bundle_id": "ST01-20260814-R17",
  "idempotency_key": "torque_controller:DC01:12341",
  "station_id": "ST01",
  "cycle_id": "20260814-000023",
  "event_type": "ACTION_CONFIRMED",
  "step_id": "S05",
  "source": "mmaction2",
  "source_instance": "camera-01",
  "sequence_no": 12341,
  "confidence": 0.96,
  "source_timestamp": "2026-08-14T10:32:15.248+08:00",
  "ingest_timestamp": "2026-08-14T10:32:15.411+08:00",
  "model_version": "action-tightening-1.0.0",
  "payload": {}
}
```

`source_timestamp` 是发生时间，`ingest_timestamp` 是系统接收时间；两个时间都必须保存。每个 source instance 使用单调 `sequence_no`，SOP Engine 通过 `idempotency_key` 去重。引擎按发生时间和每站可配置的 lateness window 排序；窗口外迟到的 Event 标记为 `LATE` 并进入人工复核，不自动改写已 `CLOSED` 的 Cycle。未关联 Cycle 的 Event 只入原始事件库，不可被错误归属。

时间字段保留毫秒精度，不等于现场具备毫秒级准确度。M0 必须按工艺风险冻结跨服务时钟偏差 SLA，并持续监测；超出 SLA 发布 `CLOCK_UNSYNCED` 系统报警，必要时令当前 Cycle 进入 `ON_HOLD`。NTP 是 V1 默认方案；只有试点需要更高精度时才评估 PTP/IEEE 1588 或硬件时间戳。

每个步骤均声明依赖、完成条件、超时、重试次数、证据窗口和异常原因模板。证据分为三层：

- **HARD**：为后续 PLC、扫码结果、电批结果、扭矩值和传感器保留；当前 Camera-only V1 不产生 HARD Evidence。
- **STATE**：垫片存在、螺丝存在、盖板到位、产品在治具；用于确认产品最终状态。
- **SOFT**：拿取、放置、锁紧、扫码等动作 AI；用于辅助确认、时序和留痕。

每条 Evidence 都必须包含 `evidence_id`、`cycle_id`、`step_id`、`value/unit`、`occurred_at`、`valid_from`、`valid_until`、`source_seq`、`quality` 与 `runtime_bundle_id`。`quality` 至少为 `VALID`、`STALE`、`INVALID` 或 `CONFLICTED`。视觉 Evidence 只有在 Cycle 绑定、序号、时间窗口、ROI、模型版本和值域均有效时才可用于裁决；旧帧、重复输出或错误 Bundle 不能完成新 Cycle 的步骤。

可见装配结果优先由 STATE 证据决定。SOFT 动作证据用于当前视觉试点的流程推进和留痕，但必须在 UI 与追溯中标记为“视觉观察”，不能解释为真实扭矩、扫码系统返回值或设备 ACK。遮挡、低置信度或模型不可用时进入 `ON_HOLD`，不猜测 PASS/FAIL。

```yaml
id: S05
name: 执行锁紧动作（视觉确认）
dependencies: [S04]
timeout_seconds: 20
completion:
  required:
    - soft: action:tightening_action_observed
  missing_policy:
    action: ON_HOLD
    reason: MISSING_REQUIRED_EVIDENCE
  conflict_policy:
    action: ON_HOLD
    reason: REVIEW_HOLD
  timeout_policy:
    action: NONCONFORMING
    reason: STEP_TIMEOUT
```

全部 required Evidence 有效才 `COMPLETE`；明确违规或超时使 `conformance_result=NONCONFORMING` 并进入 `AWAITING_DISPOSITION`；证据不足、过期或冲突进入 `ON_HOLD`，以 `REVIEW_HOLD` 等 reason code 表达原因。冲突 Event 和相关证据必须留存，不能被覆盖。

### 5.4 Runtime Configuration Bundle

`runtime_bundle` 是一个不可变、可哈希的运行配置快照，当前至少包含 SOP/步骤规则、模型与 ONNX/Engine 版本、阈值、Temporal Filter 参数、ROI、Camera Profile、时钟 SLA 和证据策略。Cycle 由 `ARMED` 转入 `RUNNING` 时冻结 Bundle ID，整个 Cycle 只能使用该 Bundle。后续启用设备时再增加 Device Mapping，不改变 Bundle 的不可变原则。

SOP、模型、阈值、ROI、相机参数和 Temporal Filter 的发布均只能在无活动 Cycle 的边界生效。新 Bundle 必须先完成审核和 Shadow/Advisory 验证；运行中不允许把 S05 的 Model v1 或 ROI v7 替换为 v2/v8。

### 5.5 数据模型

V1 至少建立：`station`、`camera`、`camera_profile`、`runtime_bundle`、`sop`、`sop_version`、`sop_step`、`cycle`、`cycle_checkpoint`、`step_execution`、`event`、`evidence`、`alarm`、`cycle_disposition`、`evidence_asset`、`model_deployment`、`user`、`audit_log`。`device_signal` 在后续启用 Device Adapter 时增加。

Event 先写入本地 append-only WAL 并完成 `fsync`，再由 SOP Engine 裁决和异步/事务方式落 PostgreSQL。Event、Cycle Checkpoint 和裁决均记录在 WAL，恢复时可重放；PostgreSQL 不可持续写入超过 M0 冻结的阈值时，发布 `DATABASE_UNAVAILABLE` 系统报警并让活跃 Cycle 进入 `ON_HOLD`，禁止输出视觉合规 PASS。关键质量 Event 的 RPO 为 0，以可恢复的本地 WAL 为边界。

视频不存入 PostgreSQL。按 `date/station/cycle` 存放原始视频、截图和事件 JSON；数据库保存路径、哈希、时长、创建时间、保留状态和关联 ID。默认仅在 `NONCONFORMING`、`ON_HOLD`、`ABORTED` 或人工保存时持久化录像，环形缓存保留前 10 秒、后录制 20 秒，保留期由质量策略配置。叠加视频为可选派生物，不作为 V1 默认存储对象。

### 5.6 API 与实时接口

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/stations` | 工位总览、在线状态、当前周期和最新报警。 |
| `GET /api/v1/stations/{id}/snapshot` | 工位详情首屏快照。 |
| `GET /api/v1/cycles/{id}` | 周期、步骤、视觉证据和结果。 |
| `POST /api/v1/cycles/{id}/dispositions` | 以审计方式提交 `REWORK`、`SCRAP` 或 `AUTHORIZED_RELEASE`。 |
| `GET /api/v1/alarms` | 报警筛选、排序、状态。 |
| `POST /api/v1/alarms/{id}/acknowledge` | 人工确认，必须写入审计日志。 |
| `GET /api/v1/evidence/{id}` | 视频、截图与事件清单的授权访问。 |
| `GET /api/v1/sops/{id}/versions/{version}` | 只读 SOP 查询。 |
| `WS /ws/v1/stations/{id}` | 当前步骤、状态、报警、相机/模型与健康度推送。 |

### 5.7 当前运行模式与后续设备扩展

Camera-only V1 最高运行到 `ADVISORY`，不提供 PLC 质量握手、自动放行或机器联锁，也不承担任何 Safety PLC 功能。安全急停、安全门和光栅始终由独立安全回路负责。

后续增加 PLC、扫码枪、电批或传感器时，实现对应 `DeviceAdapter` 并将其 Event Mapping 加入新的 Runtime Bundle。设备 Event 仍须先写 WAL、通过 Cycle Binding/Freshness/Validity 校验，再交给 SOP Engine；禁止设备 Adapter 直接写 Cycle 状态。启用 PLC Quality Handshake 必须作为独立版本重新设计、测试和验收，不能通过配置开关直接打开。

### 5.8 WebRTC 交付设计

实时媒体由 `video-runtime` 内的 DeepStream/GStreamer WebRTC Gateway（`webrtcbin`）推送，`api-server` 提供经身份验证的信令接口和短时会话令牌。V1 仅支持工厂 LAN 的 2 至 5 个并发观看者：

- 浏览器先通过授权 API 创建直播会话，再通过 WSS 交换 SDP/ICE 信令。
- 同网段使用直接 ICE；跨网段或远程访问不属于 V1，若后续需要必须独立引入并审查 TURN 服务。
- 会话断开时浏览器重连，Gateway 释放媒体资源；录像或证据回放不走 WebRTC，固定使用受授权的 MP4。
- M1 POC 验证 `Camera -> DeepStream -> WebRTC Gateway -> Chrome` 的延迟、断线恢复、CPU/GPU 消耗及 2 至 5 浏览器并发，结果写入 Benchmark 记录。

### 5.9 硬件与模型 Adapter Contract

P0 先实现稳定的 Adapter Contract，SOP Engine 只消费标准 Event，不依赖 RTSP、设备寄存器或特定模型框架。每个 Adapter 至少具备：`probe()`、`start()`、`stop()`、`health()`、`configuration_schema()` 和标准 Event 输出；连接失败必须产生 SYSTEM_ALARM，而不是伪造业务 Event。

| Adapter | P0 实现 | 现场替换实现 | 标准输出 |
| --- | --- | --- | --- |
| `CameraAdapter` | `SimulatedCameraAdapter`：循环视频/测试帧、在线与断线场景。 | `RtspCameraAdapter`、`UsbCameraAdapter`、`GigECameraAdapter`。 | 视频流、`CAMERA_ONLINE/OFFLINE/CALIBRATION_INVALID`。 |
| `ModelAdapter` | `SimulatedModelAdapter`：按测试脚本生成目标、状态和动作 Evidence。 | `DeepStreamTensorRtAdapter`。 | `OBJECT_DETECTED`、`OBJECT_STATE_CONFIRMED`、`ACTION_CONFIRMED`。 |
| `DeviceAdapter` | 仅保留合同测试实现，不绑定 `ST01-P0-R02`。 | 后续版本的 `OpcUaAdapter`、`ModbusTcpAdapter`、`TcpAdapter`、`SerialAdapter` 或厂商 SDK Adapter。 | 后续 `SCANNER_OK`、`TORQUE_OK` 等设备 Event。 |
| `EvidenceAdapter` | `LocalEvidenceAdapter`：生成测试 MP4、截图和 Event JSON。 | DeepStream Smart Recording / 已验证录像实现。 | `EVIDENCE_READY/FAILED`。 |

站点配置只描述连接和映射，不包含业务判定代码：

```yaml
station_id: ST01
field_device_scope:
  camera_only: true
camera:
  adapter: simulated # 现场改为 rtsp / usb / gige
  profile: camera-profile-v1
model:
  adapter: simulated-vision # 现场改为 deepstream_tensorrt
runtime_bundle: ST01-P0-R02
```

当前摄像头接入流程固定为：安装/连接 -> 填写配置 -> `probe()` -> 画面/ROI/Scene Integrity 验证 -> Vision Event 合同测试 -> 绑定 Runtime Bundle -> Shadow -> 现场验收。后续设备沿用独立 Adapter 流程。任何 Adapter 不得绕过 Event Journal 或直接写 Cycle 状态。

## 6. AI、数据与评测

### 6.1 模型职责

| 能力 | V1 实现 | 输出 |
| --- | --- | --- |
| 目标检测 | 经 M0.1 许可决策后的 YOLO 或 MMDetection/RTMDet -> ONNX -> TensorRT -> DeepStream | `OBJECT_DETECTED` |
| 产品/零件状态 | 检测、分类或分割，配合固定 ROI | `OBJECT_STATE_CONFIRMED` |
| 动作识别 | MMAction2 训练模型 -> ONNX -> TensorRT -> DeepStream Sequence Preprocess + `nvinfer` | `ACTION_CONFIRMED` |
| 当前步骤 | SOP Engine 基于视觉动作与产品状态 Event 推导 | `STEP_STARTED/COMPLETED` |
| 最终裁决 | SOP Engine 确定性规则与 Cycle 状态机 | `cycle_state` + `conformance_result` + `disposition` |

MMAction2 仅作为训练、验证和导出框架。生产部署优先走单一 DeepStream GPU Pipeline，避免 DeepStream 到独立 Python 推理服务之间的帧复制、IPC、缓存和时序错位。M1 必须以目标序列长度完成 DeepStream Sequence Preprocess + TensorRT 动作推理 POC；若失败，必须记录基准数据并由架构负责人审批后才可启用独立 TensorRT 服务作为受控回退。

不得把动作模型输出解释为摄像头无法观察的物理量。能够观察最终产品状态的步骤优先使用 STATE Evidence；只有动作可见而结果不可见的步骤必须明确标记“视觉动作已观察”，并在验收报告中列为能力边界。未来增加设备信号后，可通过新 SOP/Bundle 把这类步骤升级为 HARD + STATE 联合证据。

### 6.1.1 当前实现状态与 GitHub 借鉴

当前提交中的 `simulated-vision` 只生成确定性的测试 Evidence，不读取真实画面，也不包含已训练权重。USB OpenCV 已接入实时预览、JPEG 快照、MJPEG 流和相机健康状态，但不产生 Evidence。真实检测按以下链路实施：

| 检测任务 | 算法路线 | 借鉴仓库 | 当前状态 |
| --- | --- | --- | --- |
| 工件、工具、垫片、螺丝检测 | 目标检测/实例分割，固定 ROI + Tracking | [Ultralytics](https://github.com/ultralytics/ultralytics)，或许可审查通过后的 [MMDetection](https://github.com/open-mmlab/mmdetection) + RTMDet | 未实现，等待现场数据与许可决策 |
| 产品在治具、垫片存在、螺丝存在、产品移除 | 检测/分类/分割 + Temporal Filter | 同上；[IndustReal](https://github.com/TimSchoonbeek/IndustReal) 用于标注设计参考 | 未实现 |
| 拿取、放置、插入、锁紧动作 | 视频动作识别/时序窗口 | [MMAction2](https://github.com/open-mmlab/mmaction2) | 未实现 |
| 视频采集、GPU 解码、推理、Tracking、ROI、录像 | 开发环境使用 OpenCV USB 预览；正式部署使用 DeepStream + TensorRT + GStreamer | [NVIDIA DeepStream](https://github.com/NVIDIA/DeepStream)；[DeepStream Python Apps](https://github.com/NVIDIA-AI-IOT/deepstream_python_apps) 仅作示例参考 | USB 预览已实现；正式 DeepStream 未实现 |
| 步骤真正完成、装配差异、未知异常 | 后续增强 | STORM-PSR、StateDiffNet、AMNAR | 不进入当前 V1 判定链路 |

正式模型必须使用目标工位采集的数据训练和验收。开源数据集与代码只能提供算法、标注和工程参考，不能替代现场样本，也不能在未完成许可证和权重条款审查时进入商业交付。

### 6.2 AI Temporal Filter

原始动作分类输出不得直接生成 `ACTION_CONFIRMED`。每个动作模型输出必须经历下列链路：

```text
Raw Model Output
  -> Temporal Buffer
  -> Smoothing
  -> Minimum Duration
  -> Hysteresis / Cooldown
  -> ACTION_CONFIRMED
```

阈值、连续窗口数、最小持续时长、冷却时间和 ROI 由动作配置版本控制。例如，只有连续 3 个有效窗口高于阈值且满足最小持续时间时，才生成 `tighten_screw` 证据。动作被确认后仍是 SOFT Evidence，不直接改变 Step 或 Cycle 结果。

### 6.3 Model Health 与漂移监控

V1 不自动重训练，但必须识别上线后模型、场景或工艺正在退化。每个模型/类别按 Runtime Bundle 记录并对比验收基线与滚动窗口：平均及分位置信度、Low Confidence Rate、Unknown Rate、动作/步骤分布、步骤耗时、STATE 识别失败率、人工 Override 率、人工确认的误报率和关键 Evidence 缺失率。

当任一指标越过已批准阈值时，产生 `MODEL_DRIFT_WARNING` 系统报警，进入质量/AI 复核队列；它不自动改变历史结果，但可阻止新 Bundle 升级，并在风险策略要求时令新 Cycle `ON_HOLD`。

### 6.4 现场数据计划与统计验收

| 数据 | 第一轮采集目标 | 说明 |
| --- | ---: | --- |
| 正常完整周期 | 300 至 500 cycles | 覆盖人员、班次、节拍、批次与光照变化。 |
| 关键目标/状态图像 | 每类别 800 至 1,500 张 | 包含遮挡、反光、偏移、缺件和背景干扰。 |
| 动作片段 | 每动作 150 至 300 段 | 用开始、结束、人员和工位条件标注。 |
| 关键异常 | 每类至少 30 段 | 优先真实异常；受控演练样本须单独标识。 |
| Hard Negative Dataset | 首轮按混淆来源建集 | 相似工具、错误零件、临界位置、手部遮挡、反光、空治具和错误安装必须单独标记。 |

上述数量不是上线阈值。训练后必须按错误分析补充困难样本，优先修复 Hard Negative 和实际 Shadow 误报/漏报，而不是机械追加正常图片。数据集按人员、日期或生产批次划分训练/验证/测试，禁止把同一视频相邻帧随机拆到不同集合。验收集在模型锁定前冻结，并由质量负责人持有。

M5 另设独立的 Production Acceptance Run：若要在 95% 置信度下以零错误支持 False FAIL Rate 低于 1/200，至少采集 600 个独立正常 Cycle；关键违规 Recall 与 False PASS 的验收样本量必须按关键违规目标、预期发生率和可接受置信区间计算，不能以每类 30 个训练异常片段替代。

### 6.5 评测与生产模式

1. 离线回放历史视频，得到检测、状态、动作、步骤和异常混淆矩阵。
2. **SHADOW**：只记录新模型或规则结果，不影响生产放行。
3. **ADVISORY**：显示报警和推荐处置，由现场人员决定，不产生质量 HOLD/NG 输出。
4. **ENFORCING**：保留给后续含 PLC Quality Handshake 的独立版本。当前 Camera-only V1 不提供该模式，也不得输出质量互锁结果。
5. 质量人员逐条复核 NG、模型与人工不一致、漏报样本；仅在满足指标、复核结果稳定、回滚可用后切换生产模式。

### 6.6 模型制品与 TensorRT Engine

Model Manager 必须保存训练检查点、ONNX 与 Engine 元数据：

```text
model.pth / checkpoint
model.onnx
engine.target_gpu
engine.compute_capability
engine.tensorrt_version
engine.cuda_version
engine.precision
engine.sha256
```

ONNX 是跨环境部署的主要中间制品；`.engine` 是目标机器或已验证兼容目标的构建产物，不应作为可任意复制的模型文件。生产安装默认在目标 GPU、驱动、CUDA 与 TensorRT 环境中从已批准 ONNX 构建并校验 Engine；使用兼容模式或预构建 Engine 时，必须保存兼容性验证和性能结果。

## 7. UI/UX 设计方案

### 7.1 设计原则

- 面向产线监控和质量处置，信息密度高、状态明确、少装饰。
- 现场员工必须在数秒内理解“当前做什么”和“为什么不能继续”。
- 颜色只作为强化信息：绿色正常、黄色等待/预警、红色 NG、灰色离线；同时显示文字与图标。
- 主要桌面分辨率以 1366 x 768 及以上为基线；平板支持查看和处理报警，不承担复杂配置。
- 实时工位监控固定使用 WebRTC；异常证据默认使用 MP4 回放，HLS 仅作为未来长录像/低带宽回放选项。浏览器只消费流和 API，不运行 AI。

### 7.2 信息架构与权限

```text
工位监控（默认路由：/station/ST01）
异常中心
  -> 异常详情 / 证据回放
质量追溯
  -> SN 周期详情
系统配置（受控）
  -> 相机 / SOP 版本 / 模型 / 用户
```

| 角色 | 权限 |
| --- | --- |
| 操作员 | 查看当前工位、当前步骤和清晰的 NG 原因；不能修改 SOP 或删除证据。 |
| 班组长 | 查看工位、确认报警、填写处置备注、查询本班追溯。 |
| 质量人员 | 查看所有报警和证据、标注误报/有效异常、导出追溯记录；可执行 `REWORK`、`SCRAP` 或填写理由后的 `AUTHORIZED_RELEASE`。 |
| 工艺管理员 | 发布受审批的 SOP 版本、配置条件与超时。 |
| 系统管理员 | 管理相机、用户、模型部署和保留策略。 |

V1 不实现多工位矩阵、跨站 KPI 或全局运营大盘。`/dashboard` 可保留为将来路由，但只显示 ST01 单站健康摘要；避免提前实现 V2 的多工位平台能力。

报警在数据和 UI 中分为两个 Domain：`PROCESS_ALARM`（可见漏装、错序、步骤超时等视觉工艺事实）与 `SYSTEM_ALARM`（相机离线/移动、AI/数据库不可用、时钟失步、磁盘低、模型漂移）。系统报警不能计入产品不良率；必需系统能力失效时以 `ON_HOLD` 明示，不能伪装为工艺 NG。

### 7.3 页面一：工位详情（V1 首屏）

**目标**：现场实时判断当前进展、证据和异常原因。

```text
┌ Station header: ST01 | Bundle R02 | Cycle | RUNNING / ON_HOLD | 纯视觉判定 ┐
├─────────────────────────────┬─────────────────────────────────────────┤
│ 实时画面                    │ SOP 执行进度                            │
│ 检测框 / ROI / FPS / 录像    │ ✓ S01 识别产品码                        │
│                             │ ✓ S02 放入治具                          │
│                             │ ▶ S05 执行锁紧动作（视觉确认）          │
│                             │ ○ S06 完成下料                          │
├─────────────────────────────┼─────────────────────────────────────────┤
│ 当前动作、置信度、缓存状态   │ 当前步骤证据：视觉动作 / 零件状态        │
└─────────────────────────────┴─────────────────────────────────────────┘
```

- 视频左侧固定显示时间、相机状态、FPS、录像缓冲和必要检测框开关。
- 右侧步骤列表使用稳定尺寸的编号与状态图标；当前步骤高亮、已完成可回看证据。
- 证据卡同时显示来源、数值、时间与状态，例如“washer_present=true / vision-model / 10:32:14”。
- 收到 `STEP_COMPLETED` 后步骤动画仅表现状态变更，不改变页面布局。
- `CAMERA_OFFLINE`、`CAMERA_CALIBRATION_INVALID`、`AI_UNAVAILABLE` 或 `DATABASE_UNAVAILABLE` 覆盖在视频区域并说明系统限制；必需证据不可用时，将 Cycle 明示为 `ON_HOLD / 不可验证`，不能显示合规或不合规结果。
- `FAIL_HOLD`（即 `AWAITING_DISPOSITION + NONCONFORMING`）显示违规步骤、HARD/STATE/SOFT 证据矩阵和可执行的下一动作；只向授权角色展示 `REWORK`、`SCRAP`、`AUTHORIZED_RELEASE`。

### 7.4 页面二：异常中心与证据回放

**目标**：质量人员能快速理解、处置和复核 NG。

- 列表字段：时间、报警 Domain、工位、SN、SOP/Bundle、步骤、异常类型、状态、责任处置人。
- 筛选：班次、时间、Domain、工位、SOP、异常类型、未确认/已确认/已关闭。
- 详情抽屉或独立页提供前 10 秒至后 20 秒原始 MP4、截图、事件时间线和原始设备值；浏览器按 Event 叠加检测框/标签。叠加视频为可选派生物。
- NG 原因使用固定结构：`违规动作/步骤`、`未满足条件`、`已收到的证据`、`缺失或冲突证据`。
- “确认报警”“标记误报”“填写处置备注”必须记录用户、时间、理由，不允许直接删除报警。
- 对 `FAIL_HOLD` 提供 `REWORK`、`SCRAP`、`AUTHORIZED_RELEASE` 处置入口；每次处置展示生命周期、合规结果、目标处置、授权角色和证据摘要，提交后只追加审计记录。

### 7.5 页面三：SN 质量追溯

**目标**：通过一个 SN 定位完整生产过程。

- 搜索 SN、Cycle ID 或证据编号。
- 顶部并列显示生命周期、合规结果（UNKNOWN / CONFORMING / NONCONFORMING / ABORTED）和处置（NONE / REWORK / SCRAP / AUTHORIZED_RELEASE），并显示产品、工单、工位、Runtime Bundle、节拍和操作时间。
- 步骤时间线显示开始/完成时间、视觉证据、模型/阈值版本和异常。
- 对 NG 直接跳转到对应报警和录像位置。
- V1 支持 CSV 导出结构化记录；视频下载仅授予质量管理员。

### 7.6 页面四：受控配置

V1 使用表单与版本化配置，不先做通用画布式 SOP 编辑器。

- 相机：名称、地址、连接状态、分辨率、FPS、旋转、ROI、测试连接。
- SOP：只读历史版本、草稿、步骤依赖、完成条件、冲突/缺失/超时策略、异常原因模板。
- 当前 V1 不显示设备协议与信号映射；后续启用 Device Adapter 时再增加独立配置区。
- 配置发布采用“草稿 -> 审核 -> 发布 Bundle”流程；SOP、模型、阈值、ROI、相机参数和 Temporal Filter 仅在无活动 Cycle 的边界生效。

### 7.7 视觉与交互规范

| 项目 | 规范 |
| --- | --- |
| 风格 | 白色/浅灰工作台，深色左侧导航，蓝色用于可操作项。 |
| 字体 | 中文优先系统字体；数值、时间、Cycle ID 采用等宽数字字形。 |
| 面板 | 6 至 8 px 圆角、1 px 中性边框、克制阴影；不嵌套卡片。 |
| 按钮 | 图标按钮必须有悬浮提示；“确认报警”“发布”“导出”等才使用文字按钮。 |
| 实时状态 | WebSocket 推送，超过 5 秒未更新显示“数据延迟”，超过 15 秒显示连接中断。 |
| 可访问性 | 颜色之外显示状态文字、图标和原因；键盘可访问主要操作；告警可读出。 |

## 8. 设备、网络与部署

### 8.1 单工位硬件基线

- Ubuntu LTS 工业 PC 与 NVIDIA dGPU；RTX A2000 / RTX 4060 仅作为候选参考，不得直接作为采购冻结规格。
- 32 GB 内存、1 TB NVMe、千兆工厂局域网、受控 UPS。
- 固定工业相机与稳定补光；相机安装角度、焦距、曝光和白平衡在数据采集前锁定。
- 当前现场只安装一台工业相机；PLC、扫码枪、电批和传感器不属于本版硬件基线。

M1 必须先完成 Benchmark，再确定 GPU、编码和存储采购规格。基准至少包含：1 路 1920 x 1080、25/30 FPS；目标/状态模型；指定动作窗口与 ROI；WebRTC 实时预览；异常 Smart Recording；端到端告警小于 2 秒。稳态 GPU 利用率、VRAM、磁盘吞吐和容量必须留有明确 Headroom，不得用 95% 负载作为可交付状态；最终阈值、基准日志和测试版本写入硬件选型记录。

M0 同时冻结 Camera Interface：相机型号、连接协议、编码、分辨率、FPS、码率、关键帧间隔、曝光、白平衡、时间同步和重连策略。视频画面亮度/曝光漂移与帧率下降必须进入 `video-runtime` 健康指标。

Camera Profile 还必须记录 Scene Integrity 基线。优先在固定治具附近设置可检测的 ArUco Marker；无法设置时使用固定治具特征的参考图对齐。每次 ARMED 前及按配置周期计算对齐误差，超过阈值发布 `CAMERA_CALIBRATION_INVALID` 系统报警，并在后续步骤依赖该相机时使 Cycle 进入 `ON_HOLD`。

### 8.2 运维要求

- Docker Compose 随系统启动；每个服务有 readiness、liveness、重启策略和结构化日志。
- NTP 统一时间；时间字段以毫秒记录，但跨服务时间偏差以 M0 冻结的 SLA 管理和监测，超差为 `CLOCK_UNSYNCED`。
- Web/API 使用 TLS；WebSocket/WebRTC 信令必须鉴权并设置会话超时。启用 RBAC、密码策略或企业 SSO、CSRF/CORS 策略、API Rate Limit、最小化 Docker 权限和防火墙端口白名单；设备凭证通过 Secret 管理，不写入镜像或前端。
- 每日备份 PostgreSQL；证据文件使用校验和与保留策略；磁盘低水位提前告警。数据库迁移必须版本化并经预发布演练；M6 需要完成 Backup Restore Drill，验证数据库、证据索引和历史 SN 查询恢复。
- `audit_log`、质量 Event、裁决和处置采用 append-only 写入；应用数据库角色无权更新或删除已提交审计记录。现场版本由 `environment.lock`、镜像 digest、Runtime Bundle、模型和 SOP 版本共同标识，可一键回滚。
- DeepStream Smart Recording 作为 V1 首选事件录像能力；M1 必须验证其与目标相机/编码组合的稳定性，不能以文档能力替代现场验证。

## 9. 实施计划与里程碑

| 阶段 | 周期 | 交付物 | 退出条件 |
| --- | --- | --- | --- |
| P0.1 合同与核心 | 当前启动 | Event Contract、SOP Schema、Cycle/Result/Disposition、WAL、Runtime Bundle、Adapter Contract | 标准 Event 可由模拟 Adapter 端到端驱动。 |
| P0.2 平台服务 | 与 P0.1 并行 | PostgreSQL、SOP Engine、Evidence、API、审计、权限与 SYSTEM/PROCESS Alarm | 模拟数据库故障、重启、迟到/重复 Event 与授权处置均可验证。 |
| P0.3 Web 与模拟工位 | 与 P0.2 并行 | 工位详情、报警、SN 追溯、配置页、模拟视频/视觉模型场景 | 用户可在浏览器完成 CONFORMING、AWAITING_DISPOSITION、ON_HOLD、ABORTED 和 REWORK 演示。 |
| P0.4 软件基础验收 | P0 收尾 | Adapter Contract 测试、端到端模拟用例、部署包、开发者文档 | 满足 3.1，且不含任何硬编码现场参数。 |
| M0 试点冻结 | 相机到位后的第 1 周 | 视觉 SOP 表、Cycle 边界、相机位图、可见/不可见条件清单、异常清单、验收统计方案、RPO/RTO、M0.1 许可决策 | 工艺、质量、CV 三方签字确认；许可决策已关闭。 |
| M1 基础环境 | 现场第 2-3 周 | Edge 环境、真实 Camera Adapter、相机联通、WebRTC Gateway POC、GPU Benchmark、动作推理 POC | 连续运行 8 小时无关键断流，且基准、时间 SLA、硬件选型已记录。 |
| M2 数据与模型 | 现场第 4-7 周 | 标注规范、训练集、目标/状态模型、动作模型和离线报告 | 冻结测试集达到最低离线指标。 |
| M3 真实业务闭环 | 现场第 6-9 周 | 真实 DeepStream Camera/Model Adapter 与 P0 服务集成 | 可对录制数据重放并得到可解释结果，且数据库故障时能进入 ON_HOLD。 |
| M4 现场联调 | 现场第 10-12 周 | 完整实时链路、报警中心、SN 追溯、故障演练 | 首个视觉 NG 从检测到证据入库、人工处置全链路通过。 |
| M5 Shadow Mode | 现场第 13-14 周 | 人工复核台账、误报/漏报闭环、模型/场景健康、Production Acceptance Run | 达到关键步骤 Precision/Recall、False PASS/False FAIL 门槛及冻结样本量。 |
| M6 上线与支持 | 现场第 15-16 周 | 72h Soak Test、Backup Restore Drill、发布包、回滚包、Bundle/模型/SOP 版本、培训和运行手册 | Soak/恢复演练通过，质量负责人批准进入 ADVISORY；Camera-only V1 不进入 ENFORCING。 |

## 10. 测试与验收

| 测试层级 | 必测内容 |
| --- | --- |
| 单元测试 | 生命周期/合规结果/处置分离、Cycle 状态转换、依赖、超时、重复/迟到事件幂等、Evidence 新鲜度/冲突与 ON_HOLD。 |
| Adapter Contract | 所有 Simulated Adapter 的 `probe/start/stop/health/configuration_schema`、标准 Event、故障状态和配置校验。 |
| 模拟端到端 | 正常、视觉漏装、漏步、错序、冲突、数据库不可用、相机离线、REWORK/SCRAP/AUTHORIZED_RELEASE。 |
| 合同测试 | Camera/Model Adapter 到标准 Event、AI Event 到 SOP Engine、API 响应与 WebSocket；覆盖 source/ingest 时间、sequence、idempotency、schema version 和 Runtime Bundle。 |
| 视频回放 | 正常、漏步、错序、超时、遮挡、不同人员、不同节拍。 |
| 相机联调 | RTSP/USB/GigE 连接、断线重连、帧率下降、画面移动、曝光漂移和时间戳。 |
| 韧性测试 | 相机断线/移动、GPU 服务重启、数据库短暂不可用、WAL 回放、存储空间低、Web 断开、Event Replay 与 Cycle Recovery。 |
| Soak Test | 72 小时持续相机、AI 推理、WebRTC、录像触发、数据库与磁盘监控；期间不得出现未解释的 Cycle 串扰、内存增长或证据丢失。 |
| 安全与恢复 | TLS/WSS 鉴权、权限越权、审计不可篡改、密钥泄露防护、数据库迁移与 Backup Restore Drill。 |
| UI 验收 | 工位详情的生命周期、合规结果、处置、PROCESS/SYSTEM Alarm Domain、证据回放和授权处置均清楚、稳定、可审计。 |
| 现场验收 | 使用冻结测试集和真实 Shadow 记录，按预先签字的用例执行。 |

## 11. 团队与责任

| 角色 | 主要责任 |
| --- | --- |
| 工艺负责人 | 确认 SOP、步骤完成定义、异常清单和验收用例。 |
| 质量负责人 | 持有验收集、复核 Shadow 结果、批准生产判定。 |
| 自动化工程师 | 相机、照明、安装结构与网络联调；后续设备版本再承担 PLC/电批接入。 |
| CV 工程师 | 数据采集、标注、训练、评估、模型导出与 Shadow 分析。 |
| Edge/后端工程师 | DeepStream、Camera/Model Adapter、Event、SOP Engine、Evidence、数据库和 API。 |
| 前端工程师 | 监控、报警、追溯、配置页面及实时交互。 |
| 运维/安全人员 | 镜像、备份、权限、版本、网络策略和恢复演练。 |

## 12. 上线门槛与主要风险

### 上线门槛

### P0 软件基础门槛

1. 所有业务流程只依赖 Adapter Contract 与标准 Event，不依赖任何真实硬件参数。
2. 模拟场景覆盖正常、违规、证据冲突、系统故障、质量处置和 Event Recovery。
3. WAL、PostgreSQL、Runtime Bundle、审计记录和证据索引可恢复，模拟 Backup Restore Drill 通过。
4. UI、API、数据库、模拟视频和模拟视觉模型可在 Docker Compose 环境启动。
5. 软件运行模式被限制为 `SIMULATION`、`SHADOW` 或 `ADVISORY`，ENFORCING 没有可用开关。

### 现场生产门槛

1. 视觉 SOP、可见/不可见条件和异常定义已签字冻结。
2. 可见装配结果优先具有产品 STATE Evidence；只有动作可见的步骤必须明确标记“视觉观察”，不得宣称物理量或设备结果已验证。
3. 固定测试集及 Shadow Mode 均达到验收指标。
4. 录像、证据文件、SN 查询、报警确认和审计可完整演示。
5. 相机/AI/时钟/数据库故障可显式降级为 `ON_HOLD`，不会制造错误合规或错误不合规结论。
6. UI、报表和接口均把结果标识为视觉合规；Camera-only V1 不进入 ENFORCING。
7. 模型、SOP、Runtime Bundle 和服务镜像均可回滚。

### 主要风险与处置

| 风险 | 处置 |
| --- | --- |
| 相机视角、反光或遮挡导致视觉不稳定 | 在采集前完成照明、治具、ROI 与相机位优化；不以训练补偿所有现场问题。 |
| 相机被移动但仍显示在线 | 使用 ArUco 或治具特征进行 Scene Integrity 对齐；偏差超限发布 `CAMERA_CALIBRATION_INVALID` 并 ON_HOLD。 |
| 乱序、重复或重启后的 Event 串入错误 Cycle | 使用 source/ingest 时间、source instance、sequence、幂等键、lateness window 与 checkpoint/replay；不安全恢复时 ON_HOLD。 |
| 视觉证据过期、串 Cycle 或相互冲突 | 对 Evidence 执行 Cycle Binding、Freshness、Validity 和 Conflict Policy；冲突进入 REVIEW_HOLD。 |
| PostgreSQL 不可用导致追溯缺失 | WAL fsync 后才裁决；持续不可写入则 DATABASE_UNAVAILABLE + ON_HOLD，恢复后回放。 |
| 模型或工艺长期漂移 | 监控 Confidence、Unknown、步骤时长、状态失败、Override 和误报率，越界产生 MODEL_DRIFT_WARNING。 |
| 关键步骤无法用单一视觉模型可靠判断 | 缩小 Camera-only V1 工艺范围或进入 `ON_HOLD`；需要设备反馈时排入后续 Device Adapter 版本。 |
| 误报影响产线信任 | 先 Shadow Mode，质量人员复核后才切换为正式 NG。 |
| 开源许可或依赖风险 | M0.1 先关闭 Ultralytics 路线的许可决策；每个引入项建立版本、许可证、CVE 和责任台账，不通过审查不进生产。 |

## 13. 开工清单

### P0 当前开工输入

1. 本方案中冻结的 Event Contract、状态模型、Adapter Contract 和 UI 范围。
2. 用于演示的虚拟 SOP、虚拟 SN、虚拟工位、模拟视频/图像和异常场景清单。
3. 本地 Docker 开发环境与软件许可证决策记录。

P0 不需要真实相机、产品或训练数据。缺失上述真实输入不应阻塞 P0 的软件开发。

### M0 现场接入输入

1. 试点工位 SOP 与每一步“完成”的可验证定义。
2. 试点产品、可在画面中读取的 SN/产品码方案、关键异常清单及历史质量记录。
3. 相机位置、镜头、照明、连接协议、网络与固定安装方案。
4. 质量负责人签字的验收用例、数据权限与视频保留策略。
5. M0.1 已关闭的 Ultralytics Enterprise 或替代训练框架许可决策，以及已完成许可审查的仓库版本。
6. 目标工作负载的 GPU/存储 Benchmark 与已冻结的 Camera Interface。
7. Runtime Bundle、时间准确度 SLA、RPO/RTO、统计验收样本量和 SYSTEM/PROCESS Alarm Domain 的签字设计。

这些输入齐备后，M0 即可启动；在此之前，真实 Camera/Model Adapter 与训练模型保持禁用。PLC、扫码枪、电批、传感器和 ENFORCING 不属于当前 V1。
