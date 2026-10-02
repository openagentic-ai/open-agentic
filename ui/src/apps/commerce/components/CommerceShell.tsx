import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Store, ArrowUpRight, LogOut } from 'lucide-react'
import { accessToken, commerceRequest, setAccessToken } from '../lib/commerce'
import '../commerce.css'

export function CommerceShell({ children, logout }: { children: ReactNode; logout?: () => void }) {
  return <div className="commerce">
    <header className="commerce-header">
      <Link to="/merchants" className="commerce-brand"><Store size={23} /> OpenAgentic <span>商家服务</span></Link>
      <nav><Link to="/agent-commerce">找服务</Link><Link to="/operations">运营验证</Link><Link to="/connections">Agent 授权</Link><Link to="/orders">我的预约</Link><Link to="/memories">流程记忆</Link><Link to="/">Agent 控制台 <ArrowUpRight size={15} /></Link>
        {logout && <button className="quiet" onClick={logout}><LogOut size={16} />退出</button>}
      </nav>
    </header>
    <main className="commerce-main">{children}</main>
    <footer className="commerce-footer">OpenAgentic · 连接商家与每一个真实需求</footer>
  </div>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="commerce-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function LoginGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [checking, setChecking] = useState(!!accessToken())
  const [register, setRegister] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    if (accessToken()) commerceRequest('/api/auth/me')
      .then(() => { if (alive) setReady(true) })
      .catch((e: Error) => { if (alive) { setAccessToken(null); setError(e.message) } })
      .finally(() => { if (alive) setChecking(false) })
    const expired = () => { setReady(false); setChecking(false); setError('登录已过期，请重新登录') }
    window.addEventListener('commerce-auth-expired', expired)
    return () => { alive = false; window.removeEventListener('commerce-auth-expired', expired) }
  }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const data = new FormData(event.currentTarget)
    try {
      const result = await commerceRequest<{ token: string }>(`/api/auth/${register ? 'register' : 'login'}`, {
        method: 'POST', body: JSON.stringify({ email: data.get('email'), password: data.get('password') }),
      }, false)
      setAccessToken(result.token); setReady(true)
    } catch (e) { setError(e instanceof Error ? e.message : '暂时无法连接，请稍后重试') }
    finally { setBusy(false) }
  }
  const logout = () => { setAccessToken(null); setReady(false) }
  return <CommerceShell logout={ready ? logout : undefined}>
    {checking ? <p role="status">正在确认登录状态…</p> : ready ? children :
      <div className="auth-layout">
        <div><p className="eyebrow">MERCHANT WORKSPACE</p><h1>把服务发布出来，<br />让客户找到你。</h1>
          <p className="lead">开通店铺、维护服务，再把店铺链接分享给客户。</p>
          <div className="onboarding-steps"><span>01 注册账号</span><span>02 开通店铺</span><span>03 发布服务</span></div>
        </div>
        <form className="commerce-card auth-card" onSubmit={submit}>
          <h2>{register ? '注册账号' : '登录工作台'}</h2>
          <Field label="邮箱"><input name="email" type="email" autoComplete="email" required /></Field>
          <Field label="密码"><input name="password" type="password" minLength={register ? 6 : 1} maxLength={128}
            autoComplete={register ? 'new-password' : 'current-password'} required /></Field>
          {error && <p className="commerce-error" role="alert">{error}</p>}
          <button className="primary" disabled={busy}>{busy ? '请稍候…' : register ? '注册并开始' : '登录'}</button>
          <button type="button" className="quiet" onClick={() => { setRegister(!register); setError('') }}>
            {register ? '已有账号？去登录' : '还没有账号？免费注册'}</button>
        </form>
      </div>}
  </CommerceShell>
}
