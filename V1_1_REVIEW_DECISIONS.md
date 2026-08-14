# V1.1 架构评审决策记录

| 评审主题 | 决策 | 落位 |
| --- | --- | --- |
| 错误放行指标 | 采纳。增加 False PASS / Escape Rate、Critical Violation Recall、Missed NG Rate 和 False FAIL Rate；风险阈值在 M0 冻结。 | 实施方案 3、6.4、9、10 |
| PASS/FAIL 之外的状态 | 采纳。正式引入 `HOLD`、`ABORTED` 和等待处置的 `FAIL_HOLD`；证据不足禁止自动 PASS。 | 2、5.2、7.3、7.5 |
| 证据分级 | 采纳。定义 HARD、STATE、SOFT；关键步骤以 HARD/STATE 为完成裁决，SOFT 动作只支持确认与留痕。 | 5.3 |
| Cycle 生命周期 | 采纳。定义 IDLE、ARMED、RUNNING、PASS、FAIL_HOLD、HOLD、ABORTED、CLOSED 与启动、结束、重启恢复、异常处置。 | 5.2 |
| 事件乱序与恢复 | 采纳。加入 source/ingest 时间、source instance、sequence、幂等键、lateness window、checkpoint 和 Event Replay。 | 5.3、5.4、10、12 |
| 动作模型生产推理 | 采纳。MMAction2 用于训练/导出；生产优先由 DeepStream Sequence Preprocess + TensorRT `nvinfer` 在同 GPU Pipeline 运行。 | 4、5.1、6.1 |
| 动作误触发 | 采纳。模型输出必须经过 Temporal Buffer、Smoothing、Minimum Duration、Hysteresis/Cooldown 才能生成 SOFT Event。 | 6.2 |
| Ultralytics 许可 | 采纳为 M0.1 P0 决策。必须采购 Enterprise License，或切换至经审查的替代训练栈；未关闭时不得训练用于闭源交付。 | 4、9、12、13 |
| TensorRT Engine | 采纳。ONNX 是部署中间制品，Engine 是目标环境构建产物；记录 GPU、Compute Capability、CUDA/TensorRT、精度和哈希。 | 6.5 |
| 硬件规格 | 采纳。A2000/4060 仅为候选；通过目标工作负载 Benchmark 后决定采购，且保留 GPU/VRAM/存储 Headroom。 | 8.1、9 |
| DeepStream Python Apps | 采纳。仅保留为参考，明确禁止作为 V1 主工程模板。 | 4 |
| 视频和证据 | 采纳。实时固定 WebRTC，V1 回放固定原始 MP4；默认保存原始视频、截图、事件 JSON，叠加画面按浏览器或按需派生。 | 5、7、8 |
| 72 小时稳定性 | 采纳。8 小时用于 M1 开发退出；M6 需通过 72h Soak Test 才可进入 ENFORCING。 | 9、10 |
| 单工位 UI 范围 | 采纳。工位详情成为 V1 首屏；多工位矩阵和跨站 KPI 延后至 V2。 | 7.2、7.3 |
| 数据量与困难样本 | 采纳。数量改为第一轮采集目标，增加 Hard Negative Dataset 和基于错误分析的迭代要求。 | 6.3 |
| 生产模式 | 采纳。定义 SHADOW、ADVISORY、ENFORCING 三个模式及升级条件。 | 6.4 |
| NG 产品处置 | 采纳。加入 `RETRY`、`SCRAP`、`AUTHORIZED_RELEASE`、审计记录、API 和 UI 权限。 | 5.2、5.5、7.2、7.4 |

## 未采纳项

无。所有评审项均与单工位、Edge、本地裁决和 V1 交付边界一致，且可通过文档和后续工程设计在既定范围内完成。
