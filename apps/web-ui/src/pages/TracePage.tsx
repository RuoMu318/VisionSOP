import { FileSearchOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Descriptions, Drawer, Empty, Input, Table, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { CycleChart } from '../components/CycleChart'
import { ConformanceTag, LifecycleTag } from '../components/Status'
import type { CycleDetail, CycleSummary } from '../types'

export function TracePage() {
  const [serial, setSerial] = useState('')
  const [cycles, setCycles] = useState<CycleSummary[]>([])
  const [detail, setDetail] = useState<CycleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [messageApi, contextHolder] = message.useMessage()
  const [searchParams] = useSearchParams()
  const requestedCycleId = searchParams.get('cycle_id')

  const open = useCallback(async (cycleId: string | null) => {
    if (!cycleId) return
    try { setDetail(await api.cycle(cycleId)) }
    catch (error) { messageApi.error(error instanceof Error ? error.message : 'Cycle 加载失败') }
  }, [messageApi])

  const search = useCallback(async (value?: string) => {
    try { setCycles(await api.cycles(value?.trim() || undefined)) }
    catch (error) { messageApi.error(error instanceof Error ? error.message : '查询失败') }
    finally { setLoading(false) }
  }, [messageApi])
  useEffect(() => {
    if (!requestedCycleId) return
    let active = true
    void api.cycle(requestedCycleId)
      .then((result) => { if (active) setDetail(result) })
      .catch((error) => {
        if (active) messageApi.error(error instanceof Error ? error.message : 'Cycle 加载失败')
      })
    return () => { active = false }
  }, [messageApi, requestedCycleId])
  useEffect(() => {
    let active = true
    void api.cycles()
      .then((rows) => { if (active) setCycles(rows) })
      .catch((error) => {
        if (active) messageApi.error(error instanceof Error ? error.message : '查询失败')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [messageApi])

  const submitSearch = () => {
    setLoading(true)
    void search(serial)
  }

  return (
    <div className="standard-page">
      {contextHolder}
      <header className="page-title-row">
        <div><div className="section-kicker">质量数据</div><h1>SN 质量追溯</h1><p>按产品序列号回看步骤、证据、报警与处置。</p></div>
      </header>
      <div className="trace-grid">
        <section className="trace-search-panel">
          <div className="filter-bar">
            <Input
              value={serial} onChange={(event) => setSerial(event.target.value)}
              onPressEnter={submitSearch} prefix={<SearchOutlined />}
              placeholder="输入完整 SN；留空查看最近 Cycle" allowClear
            />
            <Button type="primary" onClick={submitSearch}>查询</Button>
          </div>
          <Table<CycleSummary>
            rowKey={(row) => row.cycle_id ?? 'empty'} loading={loading} dataSource={cycles}
            size="small" scroll={{ x: 760 }} pagination={{ pageSize: 10, showSizeChanger: false }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的 Cycle" /> }}
            onRow={(row) => ({ onClick: () => { void open(row.cycle_id) }, className: 'clickable-row' })}
            columns={[
              { title: 'Cycle', dataIndex: 'cycle_id', width: 200 },
              { title: 'SN', dataIndex: 'serial_number', width: 150 },
              { title: '生命周期', dataIndex: 'lifecycle', width: 120, render: (value) => <LifecycleTag value={value} /> },
              { title: '合规', dataIndex: 'conformance', width: 120, render: (value, row) => <ConformanceTag value={value} lifecycle={row.lifecycle} /> },
              { title: '处置', dataIndex: 'disposition', width: 140 },
              { title: '进度', dataIndex: 'progress_percent', width: 90, render: (value: number) => `${value}%` },
            ]}
          />
        </section>
        <section className="trace-chart-panel">
          <div className="panel-heading"><div><FileSearchOutlined /><strong> 当前结果分布</strong></div><span>{cycles.length} cycles</span></div>
          <CycleChart cycles={cycles} />
        </section>
      </div>
      <Drawer title="Cycle 追溯详情" size={560} open={Boolean(detail)} onClose={() => setDetail(null)}>
        {detail ? <>
          <Descriptions column={1} bordered size="small" items={[
            { key: 'cycle', label: 'Cycle', children: detail.cycle.cycle_id },
            { key: 'sn', label: 'SN', children: detail.cycle.serial_number },
            { key: 'lifecycle', label: '生命周期', children: <LifecycleTag value={detail.cycle.lifecycle} /> },
            { key: 'conformance', label: '合规结果', children: <ConformanceTag value={detail.cycle.conformance} lifecycle={detail.cycle.lifecycle} /> },
            { key: 'disposition', label: '处置', children: detail.cycle.disposition },
            { key: 'bundle', label: 'Runtime Bundle', children: <code>{detail.cycle.runtime_bundle_id}</code> },
          ]} />
          <Typography.Title level={5}>步骤与证据</Typography.Title>
          {detail.steps.map((step) => {
            const evidence = detail.evidence.find((item) => item.step_id === step.id)
            return <div className="trace-step" key={step.id}>
              <div><strong>{step.id} {step.name}</strong><span>{evidence?.key}</span></div>
              <Tag color={evidence?.quality === 'VALID' ? 'success' : 'warning'}>{evidence?.quality}</Tag>
            </div>
          })}
          <Typography.Title level={5}>证据资产</Typography.Title>
          {detail.evidence_assets.length ? detail.evidence_assets.map((asset) => (
            <div className="asset-row" key={asset.asset_id}><code>{asset.asset_type}</code><span>{asset.byte_size} B · {asset.sha256.slice(0, 12)}…</span></div>
          )) : <Typography.Text type="secondary">该 Cycle 未触发持久化录像策略。</Typography.Text>}
        </> : null}
      </Drawer>
    </div>
  )
}
