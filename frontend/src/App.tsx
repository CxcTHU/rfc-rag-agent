import type { CSSProperties } from 'react'
import { Bot, Database, FileSearch, LogOut, RefreshCcw, ShieldCheck, Activity } from 'lucide-react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/states'
import { AuthGate } from '@/features/auth/AuthGate'
import { useAuth } from '@/features/auth/AuthContext'
import { AskPage } from '@/features/chat/AskPage'
import { useChatWorkspace } from '@/features/chat/ChatWorkspaceContext'
import { ChatWorkspaceProvider } from '@/features/chat/ChatWorkspaceProvider'
import { EvidencePage } from '@/features/evidence/EvidencePage'
import { LibraryPage } from '@/features/library/LibraryPage'
import { QualityPage } from '@/features/quality/QualityPage'
import { TracePage } from '@/features/trace/TracePage'

const navItems = [
  { path: '/ask', label: '智能问答', icon: Bot },
  { path: '/library', label: '语料库', icon: Database },
  { path: '/evidence', label: '证据溯源', icon: FileSearch },
  { path: '/trace', label: '运行诊断', icon: Activity },
  { path: '/quality', label: '质量审阅', icon: ShieldCheck },
]

export default function App() {
  return (
    <AuthGate>
      <ChatWorkspaceProvider>
        <WorkspaceShell />
      </ChatWorkspaceProvider>
    </AuthGate>
  )
}

function WorkspaceShell() {
  const { user, signOut } = useAuth()
  const workspace = useChatWorkspace()
  const location = useLocation()
  const activeIndex = Math.max(0, navItems.findIndex((item) => location.pathname.startsWith(item.path)))
  const resetKey = `${user?.id || 'anonymous'}:${location.pathname}`

  return (
    <main className="app-shell">
      <header className="top-nav">
        <NavLink className="brand-lockup reset-button" to="/ask">
          <span className="brand-mark">R</span>
          <span><strong>RFC-RAG-Agent</strong><small>面向堆石混凝土工程知识的 RAG Agent</small></span>
        </NavLink>
        <nav className="nav-links" style={{ '--active-index': activeIndex } as CSSProperties}>
          {navItems.map((item) => {
            const Icon = item.icon
            return <NavLink key={item.path} to={item.path}><Icon size={15} />{item.label}</NavLink>
          })}
        </nav>
        <div className="header-actions">
          <Badge className="auth-badge">已登录：{user?.username}</Badge>
          <Button variant="secondary" size="sm" onClick={signOut}><LogOut size={15} />退出登录</Button>
          <Button variant="secondary" size="sm" disabled={workspace.isSubmitting || workspace.isConversationMutating} onClick={() => void workspace.refreshWorkspace()}><RefreshCcw size={15} />刷新</Button>
        </div>
      </header>
      <section className="workspace-grid">
        <ErrorBoundary resetKey={resetKey}>
          <Routes>
            <Route index element={<Navigate replace to="/ask" />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="trace" element={<TracePage />} />
            <Route path="quality" element={<QualityPage />} />
            <Route path="*" element={<Navigate replace to="/ask" />} />
          </Routes>
        </ErrorBoundary>
      </section>
    </main>
  )
}
