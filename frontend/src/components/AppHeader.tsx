
import { Button, Layout, Tag, Typography } from 'antd'
import { ApiOutlined, MenuFoldOutlined, MoonOutlined, SafetyCertificateOutlined, SunOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

const { Header } = Layout
const { Title } = Typography

interface AppHeaderProps {
  onToggleSider: () => void
  themeMode: 'light' | 'dark'
  onToggleTheme: () => void
}

export default function AppHeader({ onToggleSider, themeMode, onToggleTheme }: AppHeaderProps) {
  return (
    <Header className="app-header">
      <div className="header-left">
        <Button type="text" icon={<MenuFoldOutlined />} onClick={onToggleSider} className="sider-toggle" />
        <Link to="/" className="brand-link">
          <span className="brand-mark"><SafetyCertificateOutlined /></span>
          <span>
            <Title level={4} className="brand-title">无计划作业智能检查平台</Title>
            <span className="brand-subtitle">南方电网基建现场智能管控</span>
          </span>
        </Link>
      </div>
      <div className="header-actions">
        <Tag className="header-status" icon={<ApiOutlined />}>智能服务就绪</Tag>
        <Button className="theme-toggle" icon={themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />} onClick={onToggleTheme}>
          {themeMode === 'dark' ? '日间模式' : '夜间模式'}
        </Button>
      </div>
    </Header>
  )
}
