import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LoginGate, Field } from '../components/CommerceShell'
import { commerceRequest, money, bookingTime, type PublishedService, type Booking } from '../lib/commerce'

type Quote = { id: string; merchant_id: string; service_name: string; price_fen: number; duration_minutes: number; expires_at: string; confirmed_order_id: string | null }
export function CommerceAgentPage() { return <LoginGate><AgentSearch /></LoginGate> }
function AgentSearch() {
  const [items, setItems] = useState<PublishedService[]>([])
  const [quote, setQuote] = useState<Quote | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    setBusy(true); setError(''); setQuote(null)
    try { setItems(await commerceRequest<PublishedService[]>('/api/commerce/tools/find_services', { method: 'POST', body: JSON.stringify({ arguments: { q: data.get('q'), region: data.get('region'), limit: 50 } }) })) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function prepare(id: string) {
    setBusy(true); setError('')
    try { setQuote(await commerceRequest<Quote>('/api/commerce/tools/quote_service', { method: 'POST', body: JSON.stringify({ arguments: { service_id: id } }) })) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <><p className="eyebrow">AGENT / 开放服务入口</p><h1>找到服务，把事情办成。</h1><p className="lead">按需求和区域查询所有已发布的服务，获取报价后由你确认预约。</p>
    <p className="muted">当前使用本地工具模式。这些查询与报价工具也可交给你授权的 Agent 调用。<Link to="/connections">管理 Agent 授权 →</Link></p>
    <form className="commerce-card editor" onSubmit={search}><div className="form-grid"><Field label="需要什么服务"><input name="q" maxLength={100} placeholder="空调清洗、上门维修…" /></Field><Field label="服务区域（精确匹配）"><input name="region" maxLength={100} placeholder="例如：杭州；留空查询全部" /></Field></div><button className="primary" disabled={busy}>{busy ? '处理中…' : '查找服务'}</button></form>
    {error && <p className="commerce-error" role="alert">{error}</p>}
    {quote && <div className="commerce-card"><h2>报价已准备：{quote.service_name}</h2><p>{money(quote.price_fen)} · {quote.duration_minutes} 分钟</p><p className="muted">报价到期：{bookingTime(quote.expires_at)}。服务时间仍需商家确认。</p><Link className="primary" to={`/quotes/${quote.id}`}>查看并确认预约</Link></div>}
    <div className="service-list">{items.map(item => <article className="commerce-card" key={item.id}><h2>{item.name}</h2><p>{item.description}</p><p>{money(item.price_fen)} · {item.duration_minutes} 分钟</p><p className="muted">{item.availability_note}</p><div className="actions"><button className="primary" disabled={busy} onClick={() => prepare(item.id)}>让 Agent 准备报价</button><Link className="quiet" to={`/stores/${item.merchant_id}`}>查看商家</Link></div></article>)}</div>
    {!busy && items.length === 0 && <p className="muted">暂无结果。先让商家发布服务，再查询对应的关键词或区域。</p>}
  </>
}
export function QuoteConfirmationPage() { return <LoginGate><ConfirmQuote /></LoginGate> }
function ConfirmQuote() {
  const { quoteId } = useParams(); const [quote, setQuote] = useState<Quote | null>(null)
  const [order, setOrder] = useState<Booking | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { let alive = true; commerceRequest<Quote>(`/api/commerce/quotes/${quoteId}`).then(q => { if (alive) setQuote(q) }).catch((e: Error) => { if (alive) setError(e.message) }); return () => { alive = false } }, [quoteId])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('')
    try { setOrder(await commerceRequest<Booking>(`/api/commerce/quotes/${quoteId}/confirm`, { method: 'POST', body: JSON.stringify({ preferred_at: new Date(String(data.get('time'))).toISOString(), customer_name: data.get('name'), customer_phone: data.get('phone'), note: data.get('note'), confirmed: data.get('confirmed') === 'on' }) })) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="booking-layout"><h1>确认 Agent 准备的预约</h1>{error && <p role="alert" className="commerce-error">{error}</p>}
    {order || quote?.confirmed_order_id ? <div className="commerce-card"><h2>预约申请已提交</h2><Link className="primary" to="/orders">查看订单</Link></div> : quote && <form className="commerce-card editor" onSubmit={submit}>
      <h2>{quote.service_name}</h2><p>{money(quote.price_fen)} · {quote.duration_minutes} 分钟</p><p className="muted">到期：{bookingTime(quote.expires_at)}；如果商家改价，请重新获取报价。</p>
      <Field label="期望服务时间"><input name="time" type="datetime-local" required /></Field><Field label="联系人"><input name="name" required maxLength={100} /></Field><Field label="联系电话"><input name="phone" type="tel" required maxLength={32} /></Field><Field label="备注"><textarea name="note" maxLength={2000} /></Field>
      <label className="checkbox-field"><input name="confirmed" type="checkbox" required />我确认服务和价格，同意向商家提供上述联系信息。</label><button className="primary" disabled={busy}>{busy ? '提交中…' : '确认并提交预约'}</button>
    </form>}
  </div>
}
