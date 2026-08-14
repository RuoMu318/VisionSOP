import { AlertOutlined, CheckOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Input, Modal, Segmented, Space, Table, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { AlarmDomain, AlarmView } from '../types'

export function AlarmsPage() {
  const [domain, setDomain] = useState<'ALL' | AlarmDomain>('ALL')
  const [alarms, setAlarms] = useState<AlarmView[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<AlarmView | null>(null)
  const [reason, setReason] = useState('')
  const [messageApi, contextHolder] = message.useMessage()
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try { setAlarms(await api.alarms(domain === 'ALL' ? undefined : domain)) }
    catch (error) { messageApi.error(error instanceof Error ? error.message : '报警加载失败') }
    finally { setLoading(false) }
  }, [domain, messageApi])

  useEffect(() => {
    let active = true
    void api.alarms(domain === 'ALL' ? undefined : domain)
      .then((rows) => { if (active) setAlarms(rows) })
      .catch((error) => {
        if (active) messageApi.error(error instanceof Error ? error.message : '报警加载失败')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [domain, messageApi])

  const acknowledge = async () => {
    if (!selected || reason.trim().length < 3) return
    try {
      await api.acknowledge(selected.alarm_id, reason.trim())
      messageApi.success('报警已确认并写入审计')
      setSelected(null); setReason(''); await load()
    } catch (error) { messageApi.error(error instanceof Error ? error.message : '确认失败') }
  }

  return (
    <div className="standard-page">
      {contextHolder}
      <header className="page-title-row">
        <div><div className="section-kicker">异常与证据</div><h1>报警中心</h1><p>工艺事实与系统可用性分开管理。</p></div>
        <Button icon={<ReloadOutlined />} onClick={() => { setLoading(true); void load() }}>刷新</Button>
      </header>
      <div className="filter-bar">
        <Segmented
          value={domain}
          onChange={(value) => { setLoading(true); setDomain(value as 'ALL' | AlarmDomain) }}
          options={[{ label: '全部', value: 'ALL' }, { label: '工艺报警', value: 'PROCESS' }, { label: '系统报警', value: 'SYSTEM' }]}
        />
        <Typography.Text type="secondary">{alarms.filter((item) => !item.acknowledged).length} 条待确认</Typography.Text>
      </div>
      <Table<AlarmView>
        loading={loading} rowKey="alarm_id" dataSource={alarms} size="middle" scroll={{ x: 850 }}
        pagination={{ pageSize: 12, showSizeChanger: false }}
        columns={[
          { title: '时间', dataIndex: 'occurred_at', width: 180, render: (value: string) => new Date(value).toLocaleString('zh-CN') },
          { title: 'Domain', dataIndex: 'domain', width: 110, render: (value: AlarmDomain) => <Tag color={value === 'PROCESS' ? 'red' : 'gold'}>{value}</Tag> },
          { title: '报警代码', dataIndex: 'code', width: 210, render: (value: string) => <code>{value}</code> },
          { title: '说明', dataIndex: 'message' },
          { title: 'Cycle', dataIndex: 'cycle_id', width: 190, render: (value: string | null) => value ? <code>{value}</code> : '—' },
          { title: '状态', dataIndex: 'acknowledged', width: 100, render: (value: boolean) => value ? <Tag color="success">已确认</Tag> : <Tag color="warning">待确认</Tag> },
          {
            title: '操作', key: 'action', width: 190,
            render: (_, row) => <Space size={0}>
              <Button
                type="link" disabled={!row.cycle_id} icon={<EyeOutlined />}
                onClick={() => navigate(`/trace?cycle_id=${encodeURIComponent(row.cycle_id ?? '')}`)}
              >查看证据</Button>
              <Button type="link" disabled={row.acknowledged} icon={<CheckOutlined />} onClick={() => setSelected(row)}>确认</Button>
            </Space>,
          },
        ]}
      />
      <Modal
        title={<Space><AlertOutlined />确认报警</Space>} open={Boolean(selected)}
        okText="确认并审计" cancelText="取消" okButtonProps={{ disabled: reason.trim().length < 3 }}
        onOk={() => void acknowledge()} onCancel={() => setSelected(null)}
      >
        <Typography.Paragraph><code>{selected?.code}</code></Typography.Paragraph>
        <Typography.Paragraph type="secondary">确认仅表示已知悉，不会改变 Cycle 的原始合规结果。</Typography.Paragraph>
        <Input.TextArea rows={4} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="输入确认说明（必填）" />
      </Modal>
    </div>
  )
}
