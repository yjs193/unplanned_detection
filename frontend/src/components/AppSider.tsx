
import { DashboardOutlined, DeploymentUnitOutlined, FileDoneOutlined, FileSearchOutlined, FolderOpenOutlined, MessageOutlined, MonitorOutlined } from '@ant-design/icons'
import { Layout, Menu } from 'antd'
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
  { key: '/pilot/hj', icon: <DeploymentUnitOutlined />, label: <Link to="/pilot/hj">合景在线试点</Link> },
  {
    key: '/inspection',
    icon: <MonitorOutlined />,
    label: '无计划检查工作台',
    children: [
      { key: '/inspection/system', icon: <MessageOutlined />, label: <Link to="/inspection/system">系统交互</Link> },
      { key: '/inspection/checks', icon: <MonitorOutlined />, label: <Link to="/inspection/checks">作业检查</Link> },
    ],
  },
]

interface AppSiderProps {
  collapsed: boolean
}

export default function AppSider({ collapsed }: AppSiderProps) {
  const location = useLocation()
  const selectedKey = location.pathname === '/ticket-parser' ? '/workbench/parser' : location.pathname === '/interaction' ? '/inspection/system' : location.pathname
  return (
    <Sider width={240} collapsedWidth={84} collapsed={collapsed} theme="light" className="app-sider">
      <Menu mode="inline" selectedKeys={[selectedKey]} defaultOpenKeys={['/workbench', '/inspection']} items={menuItems} className="side-menu" />
    </Sider>
  )
}
