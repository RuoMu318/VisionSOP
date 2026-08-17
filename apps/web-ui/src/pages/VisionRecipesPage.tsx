import {
  AppstoreAddOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  ExperimentOutlined,
  PlayCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  Result,
  Select,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { CameraFeed } from '../components/CameraFeed'
import { useStation } from '../hooks/useStation'
import type { RecognizerType, VisionModel, VisionRecipe, VisionRecipeDraft, VisionTestResult } from '../types'

const recognizerOptions: Array<{ value: RecognizerType; label: string }> = [
  { value: 'CLASSICAL_CV', label: '传统视觉差分' },
  { value: 'OBJECT_DETECTION', label: '目标检测' },
  { value: 'CLASSIFICATION', label: '状态分类' },
  { value: 'SEGMENTATION', label: '分割检测' },
  { value: 'ACTION', label: '动作识别' },
]

function createRecipe(): VisionRecipeDraft {
  return {
    template_id: 'product_in_fixture',
    name: '产品放入治具检测',
    station_id: 'ST01',
    camera_id: 'ST01_CAM01',
    recognizer: { type: 'CLASSICAL_CV', model_id: 'fixture-occupancy-cv-v1', target_class: null },
    roi: { id: 'fixture_roi', x: 320, y: 180, width: 640, height: 360 },
    condition: { confidence_min: 0.85, count_min: 1, change_min: 0.12 },
    spatial_rule: 'CENTER_INSIDE_ROI',
    temporal: { confirm_frames: 5, lost_frames: 10, cooldown_ms: 1000 },
    output: { event_type: 'OBJECT_STATE_CONFIRMED', state: 'product_in_fixture' },
    sop_binding: { sop_id: 'SOP_001', step_id: 'S02', evidence_key: 'product_in_fixture' },
  }
}

function recipeStatus(status: VisionRecipe['status']) {
  return <Tag color={status === 'PUBLISHED' ? 'success' : status === 'DRAFT' ? 'gold' : 'default'}>{status}</Tag>
}

function RoiCanvas({
  recipe,
  value,
  onChange,
  disabled,
}: {
  recipe: VisionRecipe | null
  value: VisionRecipeDraft['roi']
  onChange: (roi: VisionRecipeDraft['roi']) => void
  disabled: boolean
}) {
  const station = useStation()
  const canvas = useRef<HTMLDivElement>(null)
  const [start, setStart] = useState<{ x: number; y: number } | null>(null)
  const rawWidth = 1280
  const rawHeight = 720

  const point = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = canvas.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: Math.max(0, Math.min(rawWidth, Math.round(((event.clientX - rect.left) / rect.width) * rawWidth))),
      y: Math.max(0, Math.min(rawHeight, Math.round(((event.clientY - rect.top) / rect.height) * rawHeight))),
    }
  }

  const draw = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!start) return
    const end = point(event)
    onChange({
      ...value,
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      width: Math.max(1, Math.abs(end.x - start.x)),
      height: Math.max(1, Math.abs(end.y - start.y)),
    })
  }

  if (!station.data) return null
  return (
    <div
      className="recipe-camera-canvas"
      ref={canvas}
      onPointerDown={(event) => {
        if (disabled) return
        const origin = point(event)
        event.currentTarget.setPointerCapture(event.pointerId)
        setStart(origin)
        onChange({ ...value, x: origin.x, y: origin.y, width: 1, height: 1 })
      }}
      onPointerMove={(event) => { if (!disabled) draw(event) }}
      onPointerUp={(event) => {
        if (disabled) return
        draw(event)
        setStart(null)
      }}
      aria-label="视觉模板 ROI 画布"
    >
      <CameraFeed snapshot={station.data} />
      <div
        className="recipe-roi"
        style={{
          left: `${(value.x / rawWidth) * 100}%`,
          top: `${(value.y / rawHeight) * 100}%`,
          width: `${(value.width / rawWidth) * 100}%`,
          height: `${(value.height / rawHeight) * 100}%`,
        }}
      >
        <span>{value.id || 'ROI'}</span>
      </div>
      <div className="recipe-camera-caption">
        <span>{recipe ? `${recipe.template_id} v${recipe.version}` : '新模板草稿'}</span>
        <span>{value.x}, {value.y}, {value.width} x {value.height}</span>
      </div>
    </div>
  )
}

export function VisionRecipesPage() {
  const station = useStation()
  const [form] = Form.useForm<VisionRecipeDraft>()
  const [recipes, setRecipes] = useState<VisionRecipe[]>([])
  const [models, setModels] = useState<VisionModel[]>([])
  const [selected, setSelected] = useState<VisionRecipe | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<VisionTestResult | null>(null)
  const [messageApi, contextHolder] = message.useMessage()
  const initialRecipeSelected = useRef(false)
  const recognizerType = Form.useWatch(['recognizer', 'type'], form) as RecognizerType | undefined
  const roi = Form.useWatch('roi', form) as VisionRecipeDraft['roi'] | undefined

  const fetchVisionConfiguration = useCallback(() => Promise.all([api.visionRecipes(), api.visionModels()]), [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextRecipes, nextModels] = await fetchVisionConfiguration()
      setRecipes(nextRecipes)
      setModels(nextModels)
      if (!initialRecipeSelected.current && nextRecipes.length) {
        initialRecipeSelected.current = true
        setSelected(nextRecipes[0])
        form.setFieldsValue(nextRecipes[0])
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载视觉模板')
    } finally {
      setLoading(false)
    }
  }, [fetchVisionConfiguration, form])

  useEffect(() => {
    let active = true
    void fetchVisionConfiguration()
      .then(([nextRecipes, nextModels]) => {
        if (!active) return
        setRecipes(nextRecipes)
        setModels(nextModels)
        if (!initialRecipeSelected.current && nextRecipes.length) {
          initialRecipeSelected.current = true
          setSelected(nextRecipes[0])
          form.setFieldsValue(nextRecipes[0])
        }
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : '无法加载视觉模板')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [fetchVisionConfiguration, form])

  const availableModels = useMemo(() => models.filter((model) => (
    recognizerType ? model.recognizer_types.includes(recognizerType) : true
  )), [models, recognizerType])
  const editable = !selected || selected.status === 'DRAFT'
  const currentRoi = roi ?? createRecipe().roi

  const selectRecipe = (recipe: VisionRecipe) => {
    setSelected(recipe)
    setTestResult(null)
    form.setFieldsValue(recipe)
  }

  const newRecipe = () => {
    setSelected(null)
    setTestResult(null)
    form.setFieldsValue(createRecipe())
  }

  const save = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const recipe = selected
        ? await api.updateVisionRecipe(selected.template_id, values)
        : await api.createVisionRecipe(values)
      setSelected(recipe)
      form.setFieldsValue(recipe)
      await load()
      messageApi.success('模板草稿已保存')
    } catch (reason) {
      if (reason instanceof Error) messageApi.error(reason.message)
    } finally {
      setSaving(false)
    }
  }

  const forkDraft = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const recipe = await api.createVisionDraft(selected.template_id)
      setSelected(recipe)
      form.setFieldsValue(recipe)
      await load()
      messageApi.success(`已创建 v${recipe.version} 草稿`)
    } catch (reason) {
      messageApi.error(reason instanceof Error ? reason.message : '无法创建草稿')
    } finally {
      setSaving(false)
    }
  }

  const calibrate = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const result = await api.calibrateVisionRecipe(selected.template_id, selected.version)
      if (result.calibration.status === 'CALIBRATED') messageApi.success('空治具基准图已捕获')
      else messageApi.warning(result.calibration.detail ?? result.calibration.status)
    } catch (reason) {
      messageApi.error(reason instanceof Error ? reason.message : '标定失败')
    } finally {
      setSaving(false)
    }
  }

  const test = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const response = await api.testVisionRecipe(selected.template_id, selected.version)
      setTestResult(response.result)
      if (response.result.confirmed) messageApi.success('Recipe 已生成候选状态事件')
    } catch (reason) {
      messageApi.error(reason instanceof Error ? reason.message : '测试失败')
    } finally {
      setSaving(false)
    }
  }

  const publish = async () => {
    if (!selected || selected.status !== 'DRAFT') return
    setSaving(true)
    try {
      const recipe = await api.publishVisionRecipe(selected.template_id)
      setSelected(recipe)
      form.setFieldsValue(recipe)
      await load()
      messageApi.success(`Recipe v${recipe.version} 已发布`)
    } catch (reason) {
      messageApi.error(reason instanceof Error ? reason.message : '发布失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading || station.loading) return <div className="page-loading"><Skeleton active /></div>
  if (error || station.error || !station.data) return <Result status="error" title="视觉模板加载失败" subTitle={error ?? station.error} extra={<Button onClick={() => void load()}>重试</Button>} />

  return (
    <div className="standard-page vision-recipes-page">
      {contextHolder}
      <header className="page-title-row">
        <div>
          <div className="section-kicker">Vision Recipe Engine</div>
          <h1>视觉识别模板</h1>
          <p>模型负责识别，模板定义 ROI、规则、时序确认、事件映射和 SOP 绑定。</p>
        </div>
        <Space wrap>
          {selected?.status === 'PUBLISHED' ? <Button icon={<CopyOutlined />} onClick={() => void forkDraft()} loading={saving}>创建草稿</Button> : null}
          <Button type="primary" icon={<AppstoreAddOutlined />} onClick={newRecipe}>新建模板</Button>
        </Space>
      </header>

      <Alert
        showIcon type="info" className="page-alert"
        title="Recipe 不包含产品专用推理代码"
        description="只有已发布且已标定/已部署的 Recipe 才会由 Edge Runtime 执行。测试模式不直接改变 SOP 状态。"
      />

      <div className="vision-editor-layout">
        <section className="vision-list-panel">
          <div className="panel-heading"><strong>模板版本</strong><span>{recipes.length} 个</span></div>
          {recipes.length ? <Table<VisionRecipe>
            size="small" pagination={false} rowKey={(item) => `${item.template_id}-${item.version}`}
            dataSource={recipes}
            onRow={(item) => ({ onClick: () => selectRecipe(item), className: selected?.template_id === item.template_id && selected.version === item.version ? 'selected-row' : 'clickable-row' })}
            columns={[
              { title: '模板', dataIndex: 'name', ellipsis: true },
              { title: '版本', dataIndex: 'version', width: 58, render: (value) => `v${value}` },
              { title: '状态', dataIndex: 'status', width: 108, render: recipeStatus },
            ]}
          /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未创建视觉模板" />}
        </section>

        <section className="vision-canvas-panel">
          <div className="panel-heading"><div><ExperimentOutlined /><strong> 相机与 ROI</strong></div><span>ST01_CAM01 · 1280 x 720</span></div>
          <RoiCanvas recipe={selected} value={currentRoi} onChange={(next) => form.setFieldValue('roi', next)} disabled={!editable} />
          <div className="vision-canvas-actions">
            <Button icon={<CheckCircleOutlined />} onClick={() => void calibrate()} disabled={!selected || !editable} loading={saving}>捕获空场基准</Button>
            <Button icon={<PlayCircleOutlined />} onClick={() => void test()} disabled={!selected} loading={saving}>实时测试</Button>
            {testResult ? <span className={`vision-result vision-result-${testResult.confirmed ? 'ok' : 'pending'}`}>
              {testResult.status}{testResult.confidence !== null ? ` · ${(testResult.confidence * 100).toFixed(0)}%` : ''} · 稳定 {testResult.stable_frames}
            </span> : null}
          </div>
        </section>

        <section className="vision-form-panel">
          <div className="panel-heading"><strong>{selected ? `${selected.template_id} · v${selected.version}` : '新模板'}</strong>{selected ? recipeStatus(selected.status) : <Tag>NEW</Tag>}</div>
          <Form form={form} layout="vertical" initialValues={createRecipe()} disabled={!editable} className="vision-recipe-form">
            <div className="vision-form-grid">
              <Form.Item name="name" label="模板名称" rules={[{ required: true, min: 3 }]}><Input /></Form.Item>
              <Form.Item name="template_id" label="Template ID" rules={[{ required: true, pattern: /^[a-z][a-z0-9_]{2,95}$/ }]}><Input disabled={Boolean(selected)} /></Form.Item>
              <Form.Item name="camera_id" label="相机"><Select options={[{ value: 'ST01_CAM01', label: 'ST01_CAM01' }]} /></Form.Item>
              <Form.Item name={['recognizer', 'type']} label="识别类型"><Select options={recognizerOptions} onChange={() => form.setFieldValue(['recognizer', 'model_id'], null)} /></Form.Item>
              <Form.Item name={['recognizer', 'model_id']} label="模型" rules={[{ required: recognizerType !== 'CLASSICAL_CV', message: '选择已部署模型' }]}><Select allowClear options={availableModels.map((model) => ({ value: model.model_id, label: `${model.name} · ${model.framework}` }))} /></Form.Item>
              <Form.Item name={['recognizer', 'target_class']} label="目标类别"><Input placeholder={recognizerType === 'OBJECT_DETECTION' ? '例如 product' : '传统视觉无需类别'} disabled={recognizerType === 'CLASSICAL_CV'} /></Form.Item>
              <Form.Item name={['roi', 'id']} label="ROI ID" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item label="ROI 坐标"><Space.Compact block>
                <Form.Item name={['roi', 'x']} noStyle><InputNumber min={0} addonBefore="X" /></Form.Item>
                <Form.Item name={['roi', 'y']} noStyle><InputNumber min={0} addonBefore="Y" /></Form.Item>
                <Form.Item name={['roi', 'width']} noStyle><InputNumber min={1} addonBefore="W" /></Form.Item>
                <Form.Item name={['roi', 'height']} noStyle><InputNumber min={1} addonBefore="H" /></Form.Item>
              </Space.Compact></Form.Item>
              <Form.Item name={['condition', 'confidence_min']} label="最低置信度"><InputNumber min={0} max={1} step={0.01} /></Form.Item>
              {recognizerType === 'CLASSICAL_CV' ? <Form.Item name={['condition', 'change_min']} label="变化比例阈值"><InputNumber min={0} max={1} step={0.01} /></Form.Item> : <Form.Item name={['condition', 'count_min']} label="最少目标数"><InputNumber min={1} /></Form.Item>}
              <Form.Item name={['temporal', 'confirm_frames']} label="连续确认帧"><InputNumber min={1} /></Form.Item>
              <Form.Item name={['temporal', 'lost_frames']} label="丢失确认帧"><InputNumber min={1} /></Form.Item>
              <Form.Item name={['temporal', 'cooldown_ms']} label="冷却时间 ms"><InputNumber min={0} step={100} /></Form.Item>
              <Form.Item name={['output', 'state']} label="输出状态"><Input onChange={(event) => form.setFieldValue(['sop_binding', 'evidence_key'], event.target.value)} /></Form.Item>
              <Form.Item name={['sop_binding', 'step_id']} label="绑定 SOP 步骤"><Select options={station.data.steps.map((step) => ({ value: step.id, label: `${step.id} · ${step.name}` }))} /></Form.Item>
            </div>
            <Form.Item name={['output', 'event_type']} hidden><Input /></Form.Item>
            <Form.Item name="station_id" hidden><Input /></Form.Item>
            <Form.Item name={['sop_binding', 'sop_id']} hidden><Input /></Form.Item>
            <Form.Item name={['sop_binding', 'evidence_key']} hidden><Input /></Form.Item>
            <div className="vision-form-footer">
              {editable ? <Button type="primary" icon={<SaveOutlined />} onClick={() => void save()} loading={saving}>保存草稿</Button> : <Typography.Text type="secondary">发布版本不可修改。请创建草稿后编辑。</Typography.Text>}
              {selected?.status === 'DRAFT' ? <Button onClick={() => void publish()} loading={saving}>发布 Recipe</Button> : null}
            </div>
          </Form>
        </section>
      </div>
    </div>
  )
}
