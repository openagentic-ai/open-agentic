import { useEffect, useState, type FormEvent } from 'react'
import { LoginGate, Field } from '../components/CommerceShell'
import { commerceRequest, bookingTime } from '../lib/commerce'
type Grant = { id: string; name: string; scopes: string[]; expires_at: string; revoked: boolean }
type Audit = { id: string; tool_name: string; success: boolean; status_code: number; duration_ms: number; created_at: string }
export function AgentConnectionsPage() { return <LoginGate><Connections /></LoginGate> }
function Connections() {
  const [grants, setGrants] = useState<Grant[]>([]); const [audits, setAudits] = useState<Audit[]>([])
  const [token, setToken] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function refresh() { const [g, a] = await Promise.all([commerceRequest<Grant[]>('/api/commerce/agent-grants'), commerceRequest<Audit[]>('/api/commerce/tool-audits')]); setGrants(g); setAudits(a) }
  useEffect(() => { refresh().catch((e: Error) => setError(e.message)) }, [])
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError(''); setToken('')
    try { const result = await commerceRequest<{ token: string }>('/api/commerce/agent-grants', { method: 'POST', body: JSON.stringify({ name: data.get('name'), expires_days: Number(data.get('days')), scopes: data.getAll('scopes') }) }); setToken(result.token); await refresh() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function revoke(id: string) { setBusy(true); setError(''); try { await commerceRequest(`/api/commerce/agent-grants/${id}`, { method: 'DELETE' }); setToken(''); await refresh() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  return <><p className="eyebrow">CONNECTIONS / Agent 授权</p><h1>选择 Agent 能替你做什么。</h1><p className="lead">授权绑定当前账号，随时撤销。下单和付款仍由你确认。</p>
    {error && <p className="commerce-error" role="alert">{error}</p>}
    <form className="commerce-card editor" onSubmit={create}><Field label="Agent 名称"><input name="name" maxLength={100} required placeholder="我的个人 Agent" /></Field><Field label="有效天数"><input name="days" type="number" min={1} max={30} defaultValue={7} required /></Field>
      {[['services:read','查询服务'],['quotes:write','准备报价'],['orders:read','查看我的订单状态']].map(([scope,label]) => <label className="checkbox-field" key={scope}><input type="checkbox" name="scopes" value={scope} defaultChecked={scope === 'services:read'} />{label}</label>)}<button className="primary" disabled={busy}>创建授权</button></form>
    {token && <div className="commerce-card"><h2>保存这次授权令牌</h2><p>只显示这一次。交给你信任的 Agent 后，可以收起。</p><input aria-label="Agent 授权令牌" readOnly value={token} onFocus={e => e.target.select()} /><button className="quiet" onClick={() => setToken('')}>收起令牌</button></div>}
    <h2>已创建的授权</h2><div className="service-list">{grants.map(g => <article className="commerce-card" key={g.id}><h3>{g.name}</h3><p>{g.scopes.join(' · ')}</p><p className="muted">到期：{bookingTime(g.expires_at)} · {g.revoked ? '已撤销' : new Date(g.expires_at).getTime() <= Date.now() ? '已过期' : '有效期内可用'}</p><button className="quiet" disabled={g.revoked || busy} onClick={() => revoke(g.id)}>撤销授权</button></article>)}</div>
    <div className="section-heading"><h2>调用记录</h2><button className="secondary" onClick={() => refresh().catch((e: Error) => setError(e.message))}>刷新记录</button></div>
    <div className="commerce-card">{audits.length === 0 ? <p className="muted">还没有工具调用。</p> : audits.map(a => <p key={a.id}>{bookingTime(a.created_at)} · {a.tool_name} · {a.success ? '成功' : `失败 ${a.status_code}`} · {a.duration_ms} ms</p>)}</div>
  </>
}
