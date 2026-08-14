import {
  AlertOutlined,
  ControlOutlined,
  DesktopOutlined,
  FileSearchOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { Badge, Layout, Menu, Tag, Typography } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useStation, type ConnectionState } from '../hooks/useStation'

const { Header, Sider, Content } = Layout

const items = [
  { key: '/station', icon: <DesktopOutlined />, label: '工位监控' },
  { key: '/alarms', icon: <AlertOutlined />, label: '报警中心' },
  { key: '/trace', icon: <FileSearchOutlined />, label: 'SN 追溯' },
  { key: '/config', icon: <ControlOutlined />, label: '受控配置' },
]

const connectionView: Record<ConnectionState, { status: 'success' | 'processing' | 'warning' | 'default'; text: string }> = {
  LIVE: { status: 'success', text: '边缘服务在线' },
  CONNECTING: { status: 'processing', text: '正在连接边缘服务' },
  STALE: { status: 'warning', text: '边缘数据延迟' },
  DISCONNECTED: { status: 'default', text: '边缘服务断开' },
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const station = useStation()
  const status = connectionView[station.connection]
  const mode = station.data?.station.mode ?? 'UNKNOWN'
  return (
    <Layout className="app-shell">
      <Header className="top-header">
        <div className="brand-lockup">
          <SafetyCertificateOutlined className="brand-mark" />
          <div>
            <Typography.Text className="brand-name">SOP AI</Typography.Text>
            <Typography.Text className="brand-subtitle">生产合规平台</Typography.Text>
          </div>
        </div>
        <div className="global-status">
          <Badge status={status.status} text={status.text} />
          <Tag color={mode === 'SIMULATION' ? 'gold' : mode === 'UNKNOWN' ? 'default' : 'blue'}>{mode}</Tag>
          <span className="operator-label">质量用户</span>
        </div>
      </Header>
      <Layout>
        <Sider width={184} breakpoint="lg" collapsedWidth={0} className="side-nav">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={items}
            onClick={({ key }) => navigate(key)}
          />
          <div className="side-footer">
            <span>V0.1.0 P0</span>
            <span>ST01 · R01</span>
          </div>
        </Sider>
        <Content className="page-content">{children}</Content>
      </Layout>
      <nav className="mobile-nav" aria-label="主导航">
        {items.map((item) => (
          <button
            type="button"
            key={item.key}
            className={location.pathname === item.key ? 'active' : ''}
            onClick={() => navigate(item.key)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </Layout>
  )
}
