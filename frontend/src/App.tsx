
import { useEffect, useState } from 'react'
import { ConfigProvider, Layout, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Outlet } from 'react-router-dom'
import AppHeader from './components/AppHeader'
import AppSider from './components/AppSider'

const { Content } = Layout

type ThemeMode = 'light' | 'dark'

const DEFAULT_SIDER_WIDTH = 280
const COLLAPSED_SIDER_WIDTH = 84

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [siderWidth, setSiderWidth] = useState(() => {
    const saved = Number(localStorage.getItem('sider_width') || DEFAULT_SIDER_WIDTH)
    return Number.isFinite(saved) ? Math.min(340, Math.max(240, saved)) : DEFAULT_SIDER_WIDTH
  })
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => (localStorage.getItem('theme_mode') as ThemeMode) || 'light')

  useEffect(() => {
    localStorage.setItem('theme_mode', themeMode)
    document.documentElement.setAttribute('data-theme', themeMode)
  }, [themeMode])

  useEffect(() => {
    localStorage.setItem('sider_width', String(siderWidth))
  }, [siderWidth])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: themeMode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: themeMode === 'dark' ? '#38bdf8' : '#0b4f86',
          colorLink: themeMode === 'dark' ? '#67e8f9' : '#0b5f95',
          colorInfo: themeMode === 'dark' ? '#38bdf8' : '#0b5f95',
          borderRadius: 6,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
        components: {
          Layout: { bodyBg: themeMode === 'dark' ? '#081322' : '#eaf1f8', siderBg: '#071b31', headerBg: '#082b4c' },
          Menu: { itemBorderRadius: 6, itemSelectedBg: themeMode === 'dark' ? '#0b4f86' : '#0d609d', itemSelectedColor: '#ffffff' },
          Button: { primaryShadow: 'none' },
          Table: { headerBg: themeMode === 'dark' ? '#10243b' : '#eef5fb', headerColor: themeMode === 'dark' ? '#dbeafe' : '#1d344c' },
          Card: { borderRadiusLG: 8 },
        },
      }}
    >
      <Layout className="app-shell">
        <AppHeader onToggleSider={() => setCollapsed((value) => !value)} themeMode={themeMode} onToggleTheme={() => setThemeMode((value) => (value === 'dark' ? 'light' : 'dark'))} />
        <Layout style={{ marginTop: 64 }}>
          <AppSider collapsed={collapsed} width={siderWidth} collapsedWidth={COLLAPSED_SIDER_WIDTH} onWidthChange={setSiderWidth} />
          <Content className="app-content" style={{ marginLeft: collapsed ? COLLAPSED_SIDER_WIDTH : siderWidth }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}
