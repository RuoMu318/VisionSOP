import { Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
import { AppShell } from './components/AppShell'
import { StationProvider } from './hooks/useStation'

const StationPage = lazy(() => import('./pages/StationPage').then((module) => ({ default: module.StationPage })))
const AlarmsPage = lazy(() => import('./pages/AlarmsPage').then((module) => ({ default: module.AlarmsPage })))
const TracePage = lazy(() => import('./pages/TracePage').then((module) => ({ default: module.TracePage })))
const ConfigPage = lazy(() => import('./pages/ConfigPage').then((module) => ({ default: module.ConfigPage })))
const VisionRecipesPage = lazy(() => import('./pages/VisionRecipesPage').then((module) => ({ default: module.VisionRecipesPage })))

export default function App() {
  return (
    <StationProvider>
      <AppShell>
        <Suspense fallback={<div className="page-loading"><Skeleton active /></div>}>
          <Routes>
            <Route path="/station" element={<StationPage />} />
            <Route path="/alarms" element={<AlarmsPage />} />
            <Route path="/trace" element={<TracePage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="/vision" element={<VisionRecipesPage />} />
            <Route path="*" element={<Navigate to="/station" replace />} />
          </Routes>
        </Suspense>
      </AppShell>
    </StationProvider>
  )
}
