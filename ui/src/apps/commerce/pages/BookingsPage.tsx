import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LoginGate, Field } from '../components/CommerceShell'
import { OrdersPanel } from '../components/OrdersPanel'
import { commerceRequest, money, bookingLabels, type Storefront, type Booking } from '../lib/commerce'

function requestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const text = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${text.slice(0,8)}-${text.slice(8,12)}-${text.slice(12,16)}-${text.slice(16,20)}-${text.slice(20)}`
}

function BookingForm() {
  const { merchantId, serviceId } = useParams()
  const [store, setStore] = useState<Storefront | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [order, setOrder] = useState<Booking | null>(null)
  const [id] = useState(requestId)
  const service = store?.services.find(item => item.id === serviceId)
  useEffect(() => {
    let alive = true
    commerceRequest<Storefront>(`/api/catalog/storefronts/${merchantId}`, {}, false)
      .then(item => { if (alive) setStore(item) })
      .catch((e: Error) => { if (alive) setError(e.message) })
    return () => { alive = false }
  }, [merchantId])
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!service) return
    const data = new FormData(e.currentTarget)
    setBusy(true); setError('')
    try {
      setOrder(await commerceRequest<Booking>('/api/orders', { method: 'POST', body: JSON.stringify({
        service_id: service.id, request_id: id, expected_price_fen: service.price_fen,
        preferred_at: new Date(String(data.get('time'))).toISOString(), customer_name: data.get('name'),
        customer_phone: data.get('phone'), note: data.get('note'), confirmed: data.get('confirmed') === 'on',
      }) }))
    } catch (e) { setError(e instanceof Error ? e.message : '提交失败，请重试') }
    finally { setBusy(false) }
  }
  return <div className="booking-layout">
    <Link className="quiet" to={`/stores/${merchantId}`}>← 返回店铺</Link>
    <p className="eyebrow">BOOKING / 确认预约</p><h1>{service?.name || '预约服务'}</h1>
    {error && <p className="commerce-error" role="alert">{error}</p>}
    {order ? <div className="commerce-card"><h2>预约申请已提交</h2><p>{bookingLabels[order.status]}。商家会确认你希望的服务时间。</p><p className="muted">订单编号：{order.id}</p><Link className="primary" to="/orders">查看我的预约</Link></div> : !store ? <p role="status">正在加载服务…</p> : !service ? <p className="commerce-error">服务已下架或不存在，请返回店铺选择。</p> :
      <form className="commerce-card editor" onSubmit={submit}><h2>{store.merchant.name}</h2><p>{service.description}</p>
        <div className="service-meta"><strong>{money(service.price_fen)}</strong><span>{service.duration_minutes} 分钟</span></div>
        {service.availability_note && <p className="muted">服务安排：{service.availability_note}</p>}
        <Field label="期望服务时间" hint="提交后等待商家确认时间"><input name="time" type="datetime-local" required /></Field>
        <div className="form-grid"><Field label="联系人"><input name="name" autoComplete="name" maxLength={100} required /></Field><Field label="联系电话"><input name="phone" type="tel" autoComplete="tel" maxLength={32} required /></Field></div>
        <Field label="需求备注"><textarea name="note" maxLength={2000} rows={3} placeholder="可以填写服务地点和需要商家了解的情况" /></Field>
        <label className="checkbox-field"><input type="checkbox" name="confirmed" required />我确认以上服务和价格，申请预约并将联系信息提供给该商家。</label>
        <p className="muted">当前不在线收款。服务时间以商家接单确认结果为准。</p>
        <button className="primary" disabled={busy}>{busy ? '正在提交…' : '确认并提交预约申请'}</button>
      </form>}
  </div>
}

export function BookingsPage() { return <LoginGate><BookingForm /></LoginGate> }
export function BuyerOrdersPage() { return <LoginGate><OrdersPanel /></LoginGate> }
