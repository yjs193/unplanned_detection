
import { DashboardOutlined, EyeOutlined, FileDoneOutlined, FileSearchOutlined, FolderOpenOutlined, MessageOutlined, MonitorOutlined, SafetyCertificateOutlined, SettingOutlined } from '@ant-design/icons'
import { Layout, Menu } from 'antd'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const { Sider } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: <Link to="/">仪表盘</Link> },
  {
    key: '/workbench',
    icon: <FolderOpenOutlined />,
    label: '作业票工作台',
    children: [
      { key: '/workbench/tickets', icon: <FileDoneOutlined />, label: <Link to="/workbench/tickets">作业票查看</Link> },
      { key: '/workbench/parser', icon: <FileSearchOutlined />, label: <Link to="/workbench/parser">作业票解析</Link> },
    ],
  },
  {
    key: '/inspection',
    icon: <MonitorOutlined />,
    label: '无计划检查工作台',
    children: [
      { key: '/inspection/system', icon: <MessageOutlined />, label: <Link to="/inspection/system">系统交互</Link> },
      { key: '/inspection/vision', icon: <EyeOutlined />, label: <Link to="/inspection/vision">视觉理解</Link> },
      { key: '/inspection/violations', icon: <SafetyCertificateOutlined />, label: <Link to="/inspection/violations">违规检测</Link> },
    ],
  },
  { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
]

interface AppSiderProps {
  collapsed: boolean
  width: number
  collapsedWidth: number
  onWidthChange: (width: number) => void
}

export default function AppSider({ collapsed, width, collapsedWidth, onWidthChange }: AppSiderProps) {
  const location = useLocation()
  const [resizing, setResizing] = useState(false)
  const selectedKey = location.pathname === '/ticket-parser' ? '/workbench/parser' : location.pathname === '/interaction' ? '/inspection/system' : location.pathname

  useEffect(() => {
    if (!resizing) return
    const handleMove = (event: MouseEvent) => {
      onWidthChange(Math.min(340, Math.max(240, event.clientX)))
    }
    const stop = () => setResizing(false)
    document.body.classList.add('sider-resizing')
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', stop)
    return () => {
      document.body.classList.remove('sider-resizing')
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', stop)
    }
  }, [onWidthChange, resizing])

  return (
    <Sider width={width} collapsedWidth={collapsedWidth} collapsed={collapsed} theme="dark" className="app-sider">
      <Menu mode="inline" selectedKeys={[selectedKey]} defaultOpenKeys={['/workbench', '/inspection']} items={menuItems} className="side-menu" />
      {!collapsed && <button className="sider-resize-handle" aria-label="调整侧边栏宽度" onMouseDown={() => setResizing(true)} />}
    </Sider>
  )
}
