
import { Button, Layout, Typography } from 'antd'
import { MenuFoldOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons'
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
          <span className="brand-mark">检</span>
          <Title level={4} className="brand-title">无计划作业智能检查平台</Title>
        </Link>
      </div>
      <div className="header-actions">
        <Button className="theme-toggle" icon={themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />} onClick={onToggleTheme}>
          {themeMode === 'dark' ? '日间模式' : '夜间模式'}
        </Button>
      </div>
    </Header>
  )
}
