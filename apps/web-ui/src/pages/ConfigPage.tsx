import { CloudUploadOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { Alert, Button, Descriptions, Empty, Result, Select, Skeleton, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from '../api'
import { useStation } from '../hooks/useStation'
import type { SopDefinition } from '../types'

export function ConfigPage() {
  const [selected, setSelected] = useState('S01')
  const [sop, setSop] = useState<SopDefinition | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const station = useStation()
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setSop(await api.sop()) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '配置加载失败') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => {
    let active = true
    void api.sop()
      .then((definition) => {
        if (active) { setSop(definition); setError(null) }
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : '配置加载失败')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  const steps = useMemo(() => sop?.steps ?? [], [sop])
  const flowIds = useMemo(() => ['START', ...steps.map((step) => step.id), 'END'], [steps])
  const nodes = useMemo<Node[]>(() => [
    { id: 'START', position: { x: 110, y: 0 }, data: { label: 'Start' }, className: 'flow-terminal', draggable: false },
    ...steps.map((step, index) => ({
      id: step.id, position: { x: 60, y: 85 + index * 92 },
      data: { label: `${step.id}  ${step.name}` }, className: selected === step.id ? 'flow-step selected' : 'flow-step',
      draggable: false,
    })),
    { id: 'END', position: { x: 110, y: 85 + steps.length * 92 }, data: { label: 'End' }, className: 'flow-terminal', draggable: false },
  ], [selected, steps])
  const edges = useMemo<Edge[]>(() => flowIds.slice(0, -1).map((source, index) => ({
    id: `${source}-${flowIds[index + 1]}`, source, target: flowIds[index + 1],
    markerEnd: { type: MarkerType.ArrowClosed, color: '#75817f' }, style: { stroke: '#75817f' },
  })), [flowIds])
  const onNodeClick: NodeMouseHandler = (_, node) => { if (steps.some((step) => step.id === node.id)) setSelected(node.id) }
  const step = sop?.steps.find((item) => item.id === selected)

  if (loading || station.loading) return <div className="page-loading"><Skeleton active /></div>
  if (error || station.error || !station.data) return (
    <Result
      status="error"
      title="配置加载失败"
      subTitle={error ?? station.error ?? '当前 Runtime Bundle 不可用'}
      extra={<Button type="primary" onClick={() => { void load(); void station.retry() }}>重试</Button>}
    />
  )
  if (!sop || steps.length === 0) return <Empty description="当前 Bundle 没有可显示的 SOP 步骤" />

  const bundle = station.data.runtime_bundle
  const adapterItems = Object.entries(bundle.configuration).sort(([left], [right]) => left.localeCompare(right))

  return (
    <div className="standard-page config-page">
      <header className="page-title-row">
        <div><div className="section-kicker">版本与规则</div><h1>受控配置</h1><p>查看当前冻结 Bundle、SOP 和模拟 Adapter 绑定。</p></div>
        <Button type="primary" icon={<CloudUploadOutlined />} disabled>发布新 Bundle</Button>
      </header>
      <Alert
        type="info" showIcon icon={<LockOutlined />}
        title="P0 配置为只读"
        description="真实相机、PLC、模型与 ENFORCING 开关均未接入。后续硬件通过 Adapter Contract 绑定，不修改 SOP Engine。"
        className="page-alert"
      />
      <div className="config-layout">
        <section className="flow-panel">
          <div className="panel-heading"><div><SafetyOutlined /><strong> {sop.sop_id} · Version {sop.version}</strong></div><Tag color="success">ACTIVE</Tag></div>
          <div className="flow-canvas">
            <ReactFlow nodes={nodes} edges={edges} onNodeClick={onNodeClick} fitView minZoom={0.6} maxZoom={1.4} nodesConnectable={false} elementsSelectable>
              <Background gap={20} size={1} color="#d7ddda" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </section>
        <section className="config-detail">
          <div className="panel-heading"><strong>节点配置</strong><Tag>{selected}</Tag></div>
          <Descriptions column={1} bordered size="small" items={[
            { key: 'name', label: '名称', children: step?.name ?? '—' },
            { key: 'timeout', label: '超时', children: `${step?.timeout_seconds ?? 0} 秒` },
            { key: 'evidence', label: '完成证据', children: <code>{step?.completion[0]?.key ?? '—'}</code> },
            { key: 'policy', label: '缺失策略', children: <Tag color="gold">ON_HOLD</Tag> },
            { key: 'conflict', label: '冲突策略', children: <Tag color="gold">REVIEW_HOLD</Tag> },
          ]} />
          <Typography.Title level={5}>Runtime Bundle</Typography.Title>
          <Descriptions column={1} size="small" items={[
            { key: 'bundle', label: 'Bundle ID', children: <code>{bundle.bundle_id}</code> },
            { key: 'revision', label: 'Revision', children: <code>{bundle.revision}</code> },
            { key: 'sop-version', label: 'SOP Version', children: <code>{bundle.sop_version}</code> },
            { key: 'mode', label: '运行模式', children: <Select value={station.data.station.mode} disabled options={[{ value: station.data.station.mode }]} /> },
            ...adapterItems.map(([name, value]) => ({
              key: `adapter-${name}`, label: `${name} Adapter`, children: <code>{value}</code>,
            })),
          ]} />
          <Typography.Paragraph type="secondary" className="config-note">
            现场接入顺序：填写连接配置 → probe → 信号映射测试 → Event 合同测试 → 绑定 Bundle → Shadow 验证。
          </Typography.Paragraph>
        </section>
      </div>
    </div>
  )
}
