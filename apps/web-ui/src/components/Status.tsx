import { CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled, MinusCircleFilled } from '@ant-design/icons'
import { Tag } from 'antd'
import type { ReactNode } from 'react'
import type { Conformance, Lifecycle } from '../types'

export function LifecycleTag({ value }: { value: Lifecycle }) {
  const map: Record<Lifecycle, { color: string; label: string }> = {
    IDLE: { color: 'default', label: '空闲' },
    ARMED: { color: 'processing', label: '已就绪' },
    RUNNING: { color: 'blue', label: '执行中' },
    ON_HOLD: { color: 'gold', label: '暂停 · 不可验证' },
    AWAITING_DISPOSITION: { color: 'red', label: '等待质量处置' },
    CLOSED: { color: 'default', label: '已关闭' },
  }
  const item = map[value]
  return <Tag color={item.color}>{value === 'ON_HOLD' ? <ExclamationCircleFilled /> : null} {item.label}</Tag>
}

export function ConformanceTag({ value, lifecycle }: { value: Conformance; lifecycle?: Lifecycle }) {
  if (lifecycle === 'ON_HOLD') {
    return <Tag color="gold"><MinusCircleFilled /> 不可判定</Tag>
  }
  const map: Record<Conformance, { color: string; label: string; icon: ReactNode }> = {
    UNKNOWN: { color: 'default', label: '待判定', icon: <MinusCircleFilled /> },
    CONFORMING: { color: 'success', label: '合规', icon: <CheckCircleFilled /> },
    NONCONFORMING: { color: 'error', label: '不合规', icon: <CloseCircleFilled /> },
    ABORTED: { color: 'default', label: '已中止', icon: <MinusCircleFilled /> },
  }
  const item = map[value]
  return <Tag color={item.color}>{item.icon} {item.label}</Tag>
}
