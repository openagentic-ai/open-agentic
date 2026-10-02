import { useEffect, useState } from 'react'
import { OrderAftercare } from './OrderAftercare'
import { RefreshCw } from 'lucide-react'
import { commerceRequest, money, bookingLabels, bookingTime, type Booking } from '../lib/commerce'

export function OrdersPanel({ merchantId }: { merchantId?: string }) {
  const [orders, setOrders] = useState<Booking[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const endpoint = merchantId ? `/api/merchants/${merchantId}/orders` : '/api/orders'
  async function refresh() {
    setLoading(true); setError('')
    try { setOrders(await commerceRequest<Booking[]>(endpoint)) }
    catch (e) { setError(e instanceof Error ? e.message : '订单加载失败') }
    finally { setLoading(false) }
  }
  useEffect(() => {
    let alive = true
    commerceRequest<Booking[]>(endpoint).then(items => { if (alive) setOrders(items) })
      .catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [endpoint])
  async function change(order: Booking, status: string) {
    setBusy(order.id); setError('')
    try {
      const next = await commerceRequest<Booking>(merchantId ? `${endpoint}/${order.id}/status` : `${endpoint}/${order.id}/cancel`, {
        method: 'POST', ...(merchantId ? { body: JSON.stringify({ status }) } : {}),
      })
      setOrders(old => old.map(item => item.id === next.id ? next : item))
    } catch (e) { setError(e instanceof Error ? e.message : '更新失败') }
    finally { setBusy('') }
  }
  return <section className="orders-panel">
    <div className="section-heading"><div><h2>{merchantId ? '预约订单' : '我的预约'}</h2><p className="muted">{merchantId ? '确认能提供服务后接单；完成服务后更新履约结果。' : '预约时间需商家确认。账单与售后可在每个订单下查看。'}</p></div>
      <button className="secondary" disabled={loading || !!busy} onClick={refresh}><RefreshCw size={15} />刷新</button></div>
    {error && <p role="alert" className="commerce-error">{error}</p>}
    {loading ? <p role="status">正在加载订单…</p> : orders.length === 0 ? <div className="commerce-card empty-state">还没有预约订单。</div> :
      <div className="service-list">{orders.map(order => <article className="commerce-card" key={order.id}>
        <div className="section-heading"><h3>{order.service_name}</h3><span className={`badge ${order.status === 'accepted' || order.status === 'completed' ? 'published' : ''}`}>{bookingLabels[order.status]}</span></div>
        <p>期望时间：{bookingTime(order.preferred_at)}</p><div className="service-meta"><strong>{money(order.price_fen)}</strong><span>{order.duration_minutes} 分钟</span></div>
        <p className="muted">联系人：{order.customer_name} · {order.customer_phone}</p>
        {order.note && <p className="service-description">{order.note}</p>}
        <p className="muted">订单编号：{order.id}</p>
        <div className="actions">
          {merchantId && order.status === 'pending' && <><button className="primary" disabled={!!busy} onClick={() => change(order, 'accepted')}>确认时间并接单</button><button className="quiet" disabled={!!busy} onClick={() => change(order, 'declined')}>无法接单</button></>}
          {merchantId && order.status === 'accepted' && <button className="primary" disabled={!!busy} onClick={() => change(order, 'completed')}>标记服务完成</button>}
          {!merchantId && (order.status === 'pending' || order.status === 'accepted') && <button className="quiet" disabled={!!busy} onClick={() => change(order, 'cancelled')}>取消预约</button>}
        </div>
        <OrderAftercare key={order.id + order.status} order={order} merchantId={merchantId} />
      </article>)}</div>}
  </section>
}
