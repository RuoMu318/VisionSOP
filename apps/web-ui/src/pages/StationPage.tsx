import {
  AlertOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  DatabaseOutlined,
  ExperimentOutlined,
  FileProtectOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  ToolOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Descriptions,
  Empty,
  Input,
  Modal,
  Progress,
  Result,
  Select,
  Skeleton,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { useMemo, useState } from 'react'
import { SimulatedFeed } from '../components/SimulatedFeed'
import { ConformanceTag, LifecycleTag } from '../components/Status'
import { useStation } from '../hooks/useStation'
import type { AlarmView, Disposition, EvidenceView } from '../types'

const scenarios = [
  { value: 'normal', label: '正常完成' },
  { value: 'nonconforming', label: '明确工艺 NG' },
  { value: 'hold', label: '缺少证据 HOLD' },
  { value: 'system_hold', label: '系统故障 HOLD' },
  { value: 'aborted', label: 'Cycle 中止' },
  { value: 'rework', label: '返工完成' },
]

const evidenceColumns = [
  { title: 'Step', dataIndex: 'step_id', width: 72 },
  { title: '证据', dataIndex: 'key', render: (value: string) => <code>{value}</code> },
  { title: '类型', dataIndex: 'kind', width: 84, render: (value: string) => <Tag>{value}</Tag> },
  { title: '来源', dataIndex: 'source', width: 150 },
  {
    title: '值', dataIndex: 'value', width: 82,
    render: (value: unknown) => value === null ? '—' : <code>{String(value)}</code>,
  },
  {
    title: '状态', dataIndex: 'quality', width: 112,
    render: (value: string, row: EvidenceView) => {
      if (value === 'VALID' && row.value === true) return <span className="evidence-ok"><CheckCircleFilled /> 有效</span>
      if (value === 'VALID') return <span className="evidence-ng"><CloseCircleFilled /> 值不符</span>
      if (value === 'MISSING') return <span className="evidence-pending">待采集</span>
      return <span className="evidence-hold"><AlertOutlined /> {value}</span>
    },
  },
]

function AlarmList({ alarms }: { alarms: AlarmView[] }) {
  if (!alarms.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前无报警" />
  return (
    <div className="inline-alarm-list">
      {alarms.map((alarm) => (
        <div className="inline-alarm" key={alarm.alarm_id}>
          <AlertOutlined />
          <div>
            <strong>{alarm.code}</strong>
            <span>{alarm.message}</span>
          </div>
          <Tag color={alarm.domain === 'PROCESS' ? 'red' : 'gold'}>{alarm.domain}</Tag>
        </div>
      ))}
    </div>
  )
}

export function StationPage() {
  const station = useStation()
  const [scenario, setScenario] = useState('normal')
  const [running, setRunning] = useState(false)
  const [disposition, setDisposition] = useState<Disposition | null>(null)
  const [reason, setReason] = useState('')
  const [messageApi, contextHolder] = message.useMessage()

  const alarmsByDomain = useMemo(() => ({
    PROCESS: station.data?.alarms.filter((item) => item.domain === 'PROCESS') ?? [],
    SYSTEM: station.data?.alarms.filter((item) => item.domain === 'SYSTEM') ?? [],
  }), [station.data])

  if (station.loading && !station.data) return <div className="page-loading"><Skeleton active /></div>
  if (station.error && !station.data) {
    return <Result status="error" title="无法连接 ST01" subTitle={station.error} extra={<Button onClick={station.retry}>重试</Button>} />
  }
  if (!station.data) return null
  const data = station.data
  const currentStep = data.steps.find((item) => item.id === data.cycle.current_step_id)
  const connectionColor = station.connection === 'LIVE' ? 'success' : station.connection === 'STALE' ? 'warning' : 'error'

  const run = async () => {
    setRunning(true)
    try {
      await station.runScenario(scenario)
      messageApi.success('模拟场景已执行')
    } catch {
      messageApi.error('场景执行失败')
    } finally {
      setRunning(false)
    }
  }

  const submitDisposition = async () => {
    if (!disposition || reason.trim().length < 3) return
    setRunning(true)
    try {
      await station.applyDisposition(disposition, reason.trim())
      setDisposition(null)
      setReason('')
      messageApi.success('处置已写入审计记录')
    } catch {
      messageApi.error('处置提交失败')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="station-page">
      {contextHolder}
      <section className="station-header">
        <div>
          <div className="section-kicker">工位实时监控</div>
          <h1>{data.station.station_id} · {data.station.name}</h1>
          <Space size={6} wrap>
            <Tag color="blue">Bundle {data.station.runtime_bundle_id}</Tag>
            <Tag color="gold">{data.station.mode}</Tag>
            <Tag color="cyan">纯视觉判定</Tag>
            <Tag color={connectionColor}>数据 {station.connection}</Tag>
          </Space>
        </div>
        <div className="simulation-toolbar">
          <Select value={scenario} options={scenarios} onChange={setScenario} aria-label="模拟场景" />
          <Button type="primary" icon={<PlayCircleOutlined />} loading={running} onClick={run}>运行场景</Button>
          <Tooltip title="将工位恢复为空闲状态">
            <Button icon={<ReloadOutlined />} onClick={() => void station.reset()} aria-label="重置模拟工位" />
          </Tooltip>
        </div>
      </section>

      {station.error ? <Alert type="error" showIcon title={station.error} closable className="page-alert" /> : null}
      {data.cycle.lifecycle === 'ON_HOLD' ? (
        <Alert
          type="warning" showIcon className="page-alert"
          title="Cycle 已暂停，当前证据不足或系统能力不可用"
          description="合规结果保持 UNKNOWN，授权人员复核前不会输出 PASS 或 NG。"
        />
      ) : null}
      {data.cycle.lifecycle === 'AWAITING_DISPOSITION' ? (
        <Alert
          type="error" showIcon className="page-alert"
          title="检测到明确工艺不合规，等待质量处置"
          action={<Space wrap>
            <Button size="small" onClick={() => setDisposition('REWORK')}>返工</Button>
            <Button size="small" danger onClick={() => setDisposition('SCRAP')}>报废</Button>
            <Button size="small" onClick={() => setDisposition('AUTHORIZED_RELEASE')}>授权放行</Button>
          </Space>}
        />
      ) : null}

      <section className="cycle-strip" aria-label="Cycle 状态">
        <div><span>Cycle</span><strong>{data.cycle.cycle_id ?? '尚未开始'}</strong></div>
        <div><span>SN</span><strong>{data.cycle.serial_number ?? '—'}</strong></div>
        <div><span>生命周期</span><LifecycleTag value={data.cycle.lifecycle} /></div>
        <div><span>合规结果</span><ConformanceTag value={data.cycle.conformance} lifecycle={data.cycle.lifecycle} /></div>
        <div><span>处置</span><strong>{data.cycle.disposition}</strong></div>
      </section>

      <div className="station-workspace">
        <section className="video-section">
          <div className="panel-heading">
            <div><VideoCameraOutlined /><strong> 视觉相机 CAM-01</strong></div>
            <Tag color="success">ONLINE · 25 FPS</Tag>
          </div>
          <div className="feed-frame"><SimulatedFeed snapshot={data} /></div>
          <div className="action-bar">
            <div>
              <span>当前步骤</span>
              <strong>{currentStep ? `${currentStep.id} ${currentStep.name}` : data.cycle.lifecycle === 'CLOSED' ? 'Cycle 已结束' : '等待启动'}</strong>
            </div>
            <div>
              <span>视觉动作</span>
              <strong>{currentStep ? 'simulated_action' : '—'} <small>{currentStep ? '96%' : ''}</small></strong>
            </div>
            <Progress percent={data.cycle.progress_percent} size="small" status={data.cycle.conformance === 'NONCONFORMING' ? 'exception' : 'active'} />
          </div>
        </section>

        <section className="sop-section">
          <div className="panel-heading">
            <div><FileProtectOutlined /><strong> SOP_001 · 装配流程</strong></div>
            <span>{data.cycle.progress_percent}%</span>
          </div>
          <ol className="step-list">
            {data.steps.map((step) => (
              <li key={step.id} className={`step-item step-${step.status.toLowerCase()}`}>
                <span className="step-index">{String(step.sequence).padStart(2, '0')}</span>
                <div><strong>{step.name}</strong><span>{step.id} · 超时 {step.timeout_seconds}s</span></div>
                <span className="step-status">{step.status === 'COMPLETED' ? '完成' : step.status === 'RUNNING' ? '执行中' : step.status === 'ON_HOLD' ? '暂停' : '等待'}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section className="evidence-section">
        <div className="panel-heading"><div><ExperimentOutlined /><strong> Evidence Matrix</strong></div><span>STATE / SOFT 视觉证据</span></div>
        <Table<EvidenceView>
          rowKey="step_id" columns={evidenceColumns} dataSource={data.evidence}
          pagination={false} size="small" scroll={{ x: 740 }}
        />
      </section>

      <div className="lower-grid">
        <section className="alarm-section">
          <div className="panel-heading"><div><AlertOutlined /><strong> 当前报警</strong></div><span>{data.alarms.length} 条</span></div>
          <Tabs items={[
            { key: 'process', label: `工艺报警 ${alarmsByDomain.PROCESS.length}`, children: <AlarmList alarms={alarmsByDomain.PROCESS} /> },
            { key: 'system', label: `系统报警 ${alarmsByDomain.SYSTEM.length}`, children: <AlarmList alarms={alarmsByDomain.SYSTEM} /> },
          ]} />
        </section>
        <section className="health-section">
          <div className="panel-heading"><div><ToolOutlined /><strong> 系统健康</strong></div><span>摄像头 + 视觉模型</span></div>
          <Descriptions column={1} size="small" items={[
            { key: 'camera', label: <><VideoCameraOutlined /> Camera</>, children: data.health.camera },
            { key: 'model', label: <><ExperimentOutlined /> AI Model</>, children: data.health.model },
            { key: 'database', label: <><DatabaseOutlined /> Database</>, children: data.health.database },
          ]} />
        </section>
      </div>

      <Modal
        title={`提交处置：${disposition ?? ''}`} open={Boolean(disposition)}
        okText="确认并写入审计" cancelText="取消" confirmLoading={running}
        okButtonProps={{ disabled: reason.trim().length < 3 }}
        onOk={() => void submitDisposition()} onCancel={() => setDisposition(null)}
      >
        <Typography.Paragraph type="secondary">原始 NONCONFORMING 事实不会被处置覆盖。</Typography.Paragraph>
        <Input.TextArea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} placeholder="输入处置原因（必填）" />
      </Modal>
    </div>
  )
}
