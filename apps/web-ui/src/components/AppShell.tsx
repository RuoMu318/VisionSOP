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

const { Header, Sider, Content } = Layout

const items = [
  { key: '/station', icon: <DesktopOutlined />, label: '工位监控' },
  { key: '/alarms', icon: <AlertOutlined />, label: '报警中心' },
  { key: '/trace', icon: <FileSearchOutlined />, label: 'SN 追溯' },
  { key: '/config', icon: <ControlOutlined />, label: '受控配置' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
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
          <Badge status="success" text="边缘服务在线" />
          <Tag color="gold">SIMULATION</Tag>
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
