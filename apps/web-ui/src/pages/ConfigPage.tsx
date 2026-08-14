import { CloudUploadOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { Alert, Button, Descriptions, Select, Tag, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
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

const names = ['扫描产品码', '产品放入治具', '安装垫片', '插入螺丝', '锁紧并确认扭矩', '完成下料']
const flowIds = ['START', 'S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'END']

export function ConfigPage() {
  const [selected, setSelected] = useState('S01')
  const [sop, setSop] = useState<{ sop_id: string; version: string; steps: Array<Record<string, unknown>> } | null>(null)
  useEffect(() => { void api.sop().then(setSop) }, [])
  const nodes = useMemo<Node[]>(() => [
    { id: 'START', position: { x: 110, y: 0 }, data: { label: 'Start' }, className: 'flow-terminal', draggable: false },
    ...names.map((name, index) => ({
      id: `S0${index + 1}`, position: { x: 60, y: 85 + index * 92 },
      data: { label: `S0${index + 1}  ${name}` }, className: selected === `S0${index + 1}` ? 'flow-step selected' : 'flow-step',
      draggable: false,
    })),
    { id: 'END', position: { x: 110, y: 655 }, data: { label: 'End' }, className: 'flow-terminal', draggable: false },
  ], [selected])
  const edges = useMemo<Edge[]>(() => flowIds.slice(0, -1).map((source, index) => ({
    id: `${source}-${flowIds[index + 1]}`, source, target: flowIds[index + 1],
    markerEnd: { type: MarkerType.ArrowClosed, color: '#75817f' }, style: { stroke: '#75817f' },
  })), [])
  const onNodeClick: NodeMouseHandler = (_, node) => { if (node.id.startsWith('S')) setSelected(node.id) }
  const step = sop?.steps.find((item) => item.id === selected)

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
          <div className="panel-heading"><div><SafetyOutlined /><strong> SOP_001 · Version 1.0</strong></div><Tag color="success">ACTIVE</Tag></div>
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
            { key: 'name', label: '名称', children: String(step?.name ?? names[Number(selected.slice(2)) - 1] ?? '—') },
            { key: 'timeout', label: '超时', children: `${String(step?.timeout_seconds ?? 30)} 秒` },
            { key: 'evidence', label: '完成证据', children: <code>{String((step?.completion as Array<Record<string, unknown>> | undefined)?.[0]?.key ?? '—')}</code> },
            { key: 'policy', label: '缺失策略', children: <Tag color="gold">ON_HOLD</Tag> },
            { key: 'conflict', label: '冲突策略', children: <Tag color="gold">REVIEW_HOLD</Tag> },
          ]} />
          <Typography.Title level={5}>Runtime Bundle</Typography.Title>
          <Descriptions column={1} size="small" items={[
            { key: 'bundle', label: 'Bundle ID', children: <code>ST01-P0-R01</code> },
            { key: 'mode', label: '运行模式', children: <Select value="SIMULATION" disabled options={[{ value: 'SIMULATION' }]} /> },
            { key: 'camera', label: 'CameraAdapter', children: <code>SimulatedCameraAdapter</code> },
            { key: 'model', label: 'ModelAdapter', children: <code>SimulatedModelAdapter</code> },
            { key: 'device', label: 'DeviceAdapter', children: <code>SimulatedDeviceAdapter</code> },
            { key: 'evidence-adapter', label: 'EvidenceAdapter', children: <code>LocalEvidenceAdapter</code> },
          ]} />
          <Typography.Paragraph type="secondary" className="config-note">
            现场接入顺序：填写连接配置 → probe → 信号映射测试 → Event 合同测试 → 绑定 Bundle → Shadow 验证。
          </Typography.Paragraph>
        </section>
      </div>
    </div>
  )
}
