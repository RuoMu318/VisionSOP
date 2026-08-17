# Vision Recipe Engine (M2.1)

`Vision Recipe` is the configurable layer between a generic visual recognizer and the deterministic SOP Engine. A recipe is not a product-specific algorithm and it must not directly modify SOP state.

```text
Camera frame
  -> generic recognizer / model adapter
  -> Vision Recipe (ROI, rule, threshold, temporal filter)
  -> OBJECT_STATE_CONFIRMED
  -> SOP Engine
```

## Separation of Responsibilities

| Layer | Responsibility |
| --- | --- |
| Model | What can be recognized, such as `product`, `washer`, or `screw`. |
| Vision Recipe | Where and under which rule a model result becomes a state. |
| SOP | Whether that state is valid for the current step and cycle. |

## Recipe Contract

Each recipe contains:

- station and camera identity;
- recognizer type: `CLASSICAL_CV`, `OBJECT_DETECTION`, `CLASSIFICATION`, `SEGMENTATION`, or `ACTION`;
- optional selected model and target class;
- pixel ROI and spatial rule;
- confidence/count/change thresholds and temporal filter;
- `OBJECT_STATE_CONFIRMED` output state;
- SOP ID, step ID, and required Evidence binding.

The API validates the SOP binding before a recipe can be saved. Publishing archives any prior published version and makes the published version immutable. Further edits require a cloned draft.

## Current Runtime

`fixture-occupancy-cv-v1` is the only active built-in recognizer. It compares a current ROI with a captured empty-scene reference and applies the generic `change_min`, `confidence_min`, `confirm_frames`, `lost_frames`, and `cooldown_ms` settings. It is suitable only for a fixed camera, fixture, illumination, and product presentation.

No RTMDet/MMDetection, ONNX, TensorRT, DeepStream, MMAction2, trained product model, or production Shadow acceptance result is present yet. Any configured deep-learning recipe returns `MODEL_NOT_DEPLOYED`, and an uncalibrated classic recipe returns `CALIBRATION_REQUIRED`.

## First Recipe

The first intended instance is `product_in_fixture`:

```text
Camera ST01_CAM01
  -> fixture ROI
  -> fixture-occupancy-cv-v1 or a future product detector
  -> temporal confirmation
  -> OBJECT_STATE_CONFIRMED(state=product_in_fixture)
  -> SOP_001 / S02 / product_in_fixture
```

It remains unpublished until the camera is fixed on a visible fixture, an empty-scene calibration is captured, and the recipe passes the trial test set. The currently connected camera does not show a fixture, so no production evidence is emitted.
