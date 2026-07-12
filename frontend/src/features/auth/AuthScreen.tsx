import { useRef, useState } from 'react'
import { Database, FileSearch, GitBranch, Image as ImageIcon, Loader2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { useAuth } from '@/features/auth/AuthContext'
import { cn } from '@/lib/utils'

type AuthMode = 'login' | 'register'

export function AuthScreen() {
  const auth = useAuth()
  const [mode, setMode] = useState<AuthMode>('login')
  const [visible, setVisible] = useState(false)
  const [remember, setRemember] = useState(true)
  const [identity, setIdentity] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [localError, setLocalError] = useState('')
  const identityRef = useRef<HTMLInputElement | null>(null)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLocalError('')
    try {
      if (mode === 'login') {
        await auth.signIn(identity, loginPassword, remember)
      } else {
        await auth.signUp(username, email, registerPassword, remember)
      }
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : '认证失败')
    }
  }

  const errorMessage = localError || (auth.submitError instanceof Error ? auth.submitError.message : '')
  return (
    <main className={cn('auth-screen', visible && 'is-login-visible')}>
      <div className="auth-hero">
        <div className="brand-lockup">
          <span className="brand-mark">R</span>
          <div>
            <strong>RFC-RAG-Agent</strong>
            <small>面向堆石混凝土工程知识的 RAG Agent</small>
          </div>
        </div>
        <section className="auth-copy">
          <h1>可追溯的工程知识 <span>AI Agent</span></h1>
          <p>面向堆石混凝土工程资料的检索、引用、证据和审阅工作台。</p>
          <Button
            type="button"
            className="auth-start-button"
            onClick={() => {
              setVisible(true)
              window.setTimeout(() => identityRef.current?.focus(), 260)
            }}
          >
            进入工作台
          </Button>
        </section>
        <div className="auth-capability-grid">
          <article className="auth-capability-card hybrid">
            <div className="capability-demo" aria-hidden="true">
              <div className="hybrid-path top"><span>BM25</span><i /></div>
              <div className="hybrid-path bottom"><span>Vector</span><i /></div>
              <div className="hybrid-core"><Database size={22} /><b>K</b></div>
              <div className="hybrid-rank"><span /><span /><span /></div>
            </div>
            <strong>混合检索</strong><span>BM25 + 向量召回，动态 K 与 rerank 排序</span>
          </article>
          <article className="auth-capability-card graph">
            <div className="capability-demo" aria-hidden="true">
              <div className="graph-links" />
              <span className="graph-node node-a">标准</span>
              <span className="graph-node node-b">参数</span>
              <span className="graph-node node-c">试验</span>
              <GitBranch className="graph-icon" size={18} />
            </div>
            <strong>GraphRAG</strong><span>结合实体关系，补全工程机理线索</span>
          </article>
          <article className="auth-capability-card multimodal">
            <div className="capability-demo" aria-hidden="true">
              <div className="modal-stack doc"><FileText size={18} /><span>文档</span></div>
              <div className="modal-stack image"><ImageIcon size={18} /><span>图片</span></div>
              <div className="modal-stack table"><FileSearch size={18} /><span>表格</span></div>
              <div className="modal-scan" />
            </div>
            <strong>多模态</strong><span>图表与图片证据入链，支持引用溯源</span>
          </article>
        </div>
      </div>
      <Panel className="auth-card">
        <PanelHeader className="auth-card-header">
          <div className="auth-card-kicker">RFC-RAG-Agent</div>
          <h2>{mode === 'login' ? '登录工作台' : '创建账号'}</h2>
        </PanelHeader>
        <form className="auth-form" onSubmit={submit}>
          <div className="auth-tabs">
            <Button type="button" variant={mode === 'login' ? 'default' : 'secondary'} onClick={() => setMode('login')}>登录</Button>
            <Button type="button" variant={mode === 'register' ? 'default' : 'secondary'} onClick={() => setMode('register')}>创建账号</Button>
          </div>
          {mode === 'register' ? (
            <>
              <label className="auth-field"><span>用户名</span><Input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="EthanCui" /></label>
              <label className="auth-field"><span>邮箱</span><Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" /></label>
              <label className="auth-field"><span>密码</span><Input value={registerPassword} onChange={(event) => setRegisterPassword(event.target.value)} type="password" placeholder="至少 8 位字符" /></label>
            </>
          ) : (
            <>
              <label className="auth-field"><span>用户名或邮箱</span><Input ref={identityRef} value={identity} onChange={(event) => setIdentity(event.target.value)} placeholder="输入账号" /></label>
              <label className="auth-field"><span>密码</span><Input value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} type="password" placeholder="输入密码" /></label>
            </>
          )}
          <label className="remember-row"><input checked={remember} onChange={(event) => setRemember(event.target.checked)} type="checkbox" /><span>记住登录状态</span></label>
          <Button type="submit" disabled={auth.isSubmitting}>
            {auth.isSubmitting ? <Loader2 className="spin" size={16} /> : null}
            {mode === 'login' ? '登录' : '创建账号'}
          </Button>
          {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        </form>
      </Panel>
    </main>
  )
}
