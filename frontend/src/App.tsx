
import { useEffect, useState } from 'react'
import { ConfigProvider, Layout, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Outlet } from 'react-router-dom'
import AppHeader from './components/AppHeader'
import AppSider from './components/AppSider'

const { Content } = Layout

type ThemeMode = 'light' | 'dark'

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => (localStorage.getItem('theme_mode') as ThemeMode) || 'light')

  useEffect(() => {
    localStorage.setItem('theme_mode', themeMode)
    document.documentElement.setAttribute('data-theme', themeMode)
  }, [themeMode])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: themeMode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: themeMode === 'dark' ? '#22d3ee' : '#1769aa',
          borderRadius: 6,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
        components: {
          Layout: { bodyBg: themeMode === 'dark' ? '#111827' : '#f3f6fb', siderBg: themeMode === 'dark' ? '#0f172a' : '#ffffff', headerBg: themeMode === 'dark' ? '#111827' : '#ffffff' },
          Card: { borderRadiusLG: 8 },
        },
      }}
    >
      <Layout className="app-shell">
        <AppHeader onToggleSider={() => setCollapsed((value) => !value)} themeMode={themeMode} onToggleTheme={() => setThemeMode((value) => (value === 'dark' ? 'light' : 'dark'))} />
        <Layout style={{ marginTop: 64 }}>
          <AppSider collapsed={collapsed} />
          <Content className="app-content" style={{ marginLeft: collapsed ? 84 : 240 }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}
