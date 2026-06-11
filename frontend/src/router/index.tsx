
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Spin } from 'antd'
import App from '../App'

const DashboardPage = lazy(() => import('../pages/DashboardPage'))
const TicketListPage = lazy(() => import('../pages/TicketListPage'))
const TicketParserPage = lazy(() => import('../pages/TicketParserPage'))
const InteractionPage = lazy(() => import('../pages/InteractionPage'))
const WorkInspectionPage = lazy(() => import('../pages/WorkInspectionPage'))
const ViolationDetectionPage = lazy(() => import('../pages/ViolationDetectionPage'))
const VisionUnderstandingPage = lazy(() => import('../pages/VisionUnderstandingPage'))
const PilotWorkflowPage = lazy(() => import('../pages/PilotWorkflowPage'))
const DocxPage = lazy(() => import('../pages/DocxPage'))
const SettingsPage = lazy(() => import('../pages/SettingsPage'))

const Loading = () => (
  <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <Spin size="large" />
  </div>
)

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<App />}>
        <Route path="/" element={<Suspense fallback={<Loading />}><DashboardPage /></Suspense>} />
        <Route path="/workbench/tickets" element={<Suspense fallback={<Loading />}><TicketListPage /></Suspense>} />
        <Route path="/workbench/parser" element={<Suspense fallback={<Loading />}><TicketParserPage /></Suspense>} />
        <Route path="/ticket-parser" element={<Navigate to="/workbench/parser" replace />} />
        <Route path="/interaction" element={<Navigate to="/inspection/system" replace />} />
        <Route path="/inspection/system" element={<Suspense fallback={<Loading />}><InteractionPage /></Suspense>} />
        <Route path="/pilot/hj" element={<Suspense fallback={<Loading />}><PilotWorkflowPage /></Suspense>} />
        <Route path="/inspection/vision" element={<Suspense fallback={<Loading />}><VisionUnderstandingPage /></Suspense>} />
        <Route path="/inspection/violations" element={<Suspense fallback={<Loading />}><ViolationDetectionPage /></Suspense>} />
        <Route path="/inspection/checks" element={<Suspense fallback={<Loading />}><WorkInspectionPage /></Suspense>} />
        <Route path="/docx" element={<Suspense fallback={<Loading />}><DocxPage /></Suspense>} />
        <Route path="/settings" element={<Suspense fallback={<Loading />}><SettingsPage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
