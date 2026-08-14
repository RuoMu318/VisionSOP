# 工业 SOP 合规检测 GitHub 仓库登记表

> 本清单以项目已核验的仓库为准。它是技术选型和研究的登记表，不代表全部会被直接合并、镜像或部署到产品中。

## 1. 产品核心与优先级

| 优先级 | 仓库 | 产品角色 | 使用阶段 |
| --- | --- | --- | --- |
| P0 | [NVIDIA DeepStream](https://github.com/NVIDIA/DeepStream) | 相机、RTSP、多路视频、GPU 解码、TensorRT、Tracking 和实时 Pipeline | V1 部署底座 |
| P0 | [Ultralytics](https://github.com/ultralytics/ultralytics) | 工件、手、工具、螺丝、垫片、治具等目标/状态检测 | V1 模型训练与验证 |
| P0 | [MMAction2](https://github.com/open-mmlab/mmaction2) | 拿取、放置、扫码、插入、锁紧、检查等动作识别 | V1/V2 |
| P1 | [STORM-PSR](https://github.com/shaohsuanhung/STORM-PSR) | 判断一个 SOP 步骤是否真正完成 | V3 增强 |
| P1 | [IndustReal](https://github.com/TimSchoonbeek/IndustReal) | 工业装配步骤、状态与错误数据的标注和实验参考 | 数据与研发参考 |
| P2 | [AMNAR](https://github.com/iSEE-Laboratory/AMNAR) | 动作分割与在线流程异常检测 | V4 研究与增强 |
| P2 | [Differentiable Task Graph Learning](https://github.com/fpv-iplab/Differentiable-Task-Graph-Learning) | 复杂 SOP、分支流程和前后依赖关系 | V4 研究与增强 |
| P1 | [Find My Assembly Mistakes / StateDiffNet](https://github.com/Dan-Leh/find-my-assembly-mistakes) | 漏装、错装和装配状态差异定位 | V3 增强 |

## 1.1 V1 目标检测许可决策

V1 在开始任何目标/状态模型训练前必须关闭 M0.1 许可决策。Ultralytics 社区软件/模型路线涉及 AGPL-3.0 与 Enterprise License 的商业使用边界，不能仅在上线前笼统检查。项目必须选择并记录以下路径之一：

1. 取得适用于目标交付方式的 Ultralytics Enterprise License，并继续使用 [Ultralytics](https://github.com/ultralytics/ultralytics)。
2. 采用经许可证审查的替代训练框架，例如 [MMDetection](https://github.com/open-mmlab/mmdetection) + RTMDet。

无论选择哪一路线，预训练权重、训练数据、模型导出物和最终部署方式仍需独立完成许可与合规审查。

## 2. SOP、步骤识别与流程错误研究

| 仓库 | 研究用途 | 产品使用原则 |
| --- | --- | --- |
| [STORM-PSR](https://github.com/shaohsuanhung/STORM-PSR) | SOP 步骤正确完成和顺序识别 | 用于补强“动作发生不等于完成”，不取代确定性 SOP Engine。 |
| [IndustReal](https://github.com/TimSchoonbeek/IndustReal) | 工业装配、状态、执行错误数据集 | 指导内部采集、标注和评测设计。 |
| [PREGO](https://github.com/aleflabo/PREGO) | 在线流程错误检测、预测下一动作 | 作为对照研究；已知 SOP 的 V1 不以预测模型做规则判定。 |
| [AMNAR](https://github.com/iSEE-Laboratory/AMNAR) | 动作分割与在线异常检测 | 后续发现未知或非标准操作。 |
| [Differentiable Task Graph Learning](https://github.com/fpv-iplab/Differentiable-Task-Graph-Learning) | 学习步骤依赖、复杂流程和在线错误 | 仅在出现并行/分支 SOP 时评估。 |
| [GTG2Vid](https://github.com/robert80203/GTG2Vid) | Generalized Task Graph 与流程错误识别 | 复杂流程研究参考。 |
| [Find My Assembly Mistakes / StateDiffNet](https://github.com/Dan-Leh/find-my-assembly-mistakes) | 装配状态差异与错误位置定位 | 用于 V3 产品状态验证。 |

## 3. 动作识别与时序分割

| 仓库 | 用途 | 备注 |
| --- | --- | --- |
| [MMAction2](https://github.com/open-mmlab/mmaction2) | 动作识别、动作定位、视频理解 | 当前主视频 AI 框架。 |
| [MS-TCN2](https://github.com/sj-li/MS-TCN2) | 长视频动作时序分割 | 连续工序切分候选方案。 |
| [ASFormer](https://github.com/ChinaYi/ASFormer) | Transformer 动作时序分割 | 时序模型候选方案。 |
| [Assembly101 Action Recognition](https://github.com/assembly-101/assembly101-action-recognition) | 装配动作模型与 Benchmark | 模型评测和迁移学习参考。 |

## 4. 实时工业部署与训练框架

| 仓库 | 用途 | 采用边界 |
| --- | --- | --- |
| [NVIDIA DeepStream](https://github.com/NVIDIA/DeepStream) | 视频采集、解码、TensorRT 推理、Tracking、ROI 和多流管理 | 正式 Edge 视频底座。 |
| [DeepStream Python Apps](https://github.com/NVIDIA-AI-IOT/deepstream_python_apps) | Python 示例、RTSP 和推理程序参考 | 仅作示例参考；新实现优先采用 DeepStream Service Maker，避免新建基于已弃用 `pyds` 的核心代码。 |
| [OpenVINO Open Model Zoo](https://github.com/openvinotoolkit/open_model_zoo) | Intel 平台视觉/动作 Demo | 作为非 NVIDIA 硬件路线的备选，不纳入当前基线。 |
| [PyTorch](https://github.com/pytorch/pytorch) | 训练、微调和模型开发 | 模型研发基础框架。 |
| [Ultralytics](https://github.com/ultralytics/ultralytics) | YOLO 检测、分割、姿态和跟踪 | V1 目标/状态视觉模型首选实现。 |

## 5. 数据集与装配研究参考

| 仓库 | 用途 |
| --- | --- |
| [HA-ViD](https://github.com/iai-hrc/ha-vid) | 工业装配视频，覆盖动作识别和动作分割。 |
| [InHARD](https://github.com/vhavard/InHARD) | Industrial Human Action Recognition 数据集。 |
| [IKEA Assembly in the Wild Dataset](https://github.com/DavidZhang73/IKEAAssemblyInTheWildDataset) | 真实环境装配视频与步骤研究。 |
| [IKEA Manuals at Work](https://github.com/yunongLiu1/IKEA-Manuals-at-Work) | 装配说明书与真实装配视频关联研究。 |

这些数据集用于算法验证、标注方案和实验设计参考；正式模型验收必须以目标工位采集的现场数据为准，并遵守各数据集的具体许可条款。

## 6. PPE / 工业安全合规扩展

这些项目服务于安全帽、反光衣等 PPE 视觉检查，不用于判断生产 SOP 顺序。PPE 属于可选产品扩展，且不得替代 Safety PLC、安全门或安全光栅。

| 仓库 | 用途 |
| --- | --- |
| [PPE Compliance Detection YOLO](https://github.com/gagangkrishna/PPE-Compliance-Detection-YOLO) | PPE 合规检测。 |
| [Industrial Safety Detection YOLOv8](https://github.com/krtik-2404/industrial-safety-detection-yolov8) | 工业安全目标检测。 |
| [CV Safety Engine](https://github.com/M-AlAteegi/cv-safety-engine) | PPE / 工业安全视觉检测。 |
| [PPEv2](https://github.com/jatinpochiraju/ppev2) | PPE 视觉检测参考。 |
| [PPE Safety Detection AI](https://github.com/prodbykosta/ppe-safety-detection-ai) | PPE 视觉检测参考。 |

## 7. 推荐研究顺序

```text
PyTorch
  -> Ultralytics
  -> MMAction2
  -> IndustReal
  -> STORM-PSR
  -> AMNAR / Task Graph
  -> DeepStream
  -> 现场部署与验收
```

## 8. 引用与使用约束

1. 开源仓库优先作为实现、实验或数据设计参考；不默认将其代码作为生产依赖。
2. 引入前应固定 commit / release、校验许可证、维护状态、依赖 CVE、模型权重许可及数据集使用范围。
3. 生产系统的 PASS/FAIL 由自研 SOP Engine 和受控设备信号决定，研究模型只能提供标准化证据事件。
4. 过去提到的 `SANKAAKASH/ppe-detection-yolo` 未在本次核验清单中，后续不作为项目来源引用。
