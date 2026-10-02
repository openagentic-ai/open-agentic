import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MapPin, Clock } from 'lucide-react'
import { CommerceShell } from '../components/CommerceShell'
import { commerceRequest, money, type Storefront } from '../lib/commerce'

export function StorefrontPage() {
  const { merchantId } = useParams()
  const [store, setStore] = useState<Storefront | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    setStore(null); setError('')
    commerceRequest<Storefront>(`/api/catalog/storefronts/${merchantId}`, {}, false)
      .then(item => { if (alive) setStore(item) })
      .catch((e: Error) => { if (alive) setError(e.message) })
    return () => { alive = false }
  }, [merchantId])
  return <CommerceShell>
    {error ? <div className="commerce-error" role="alert">{error}</div> : !store ? <p role="status">正在加载店铺…</p> : <>
      <div className="storefront-hero"><p className="eyebrow">LOCAL SERVICES / 商家服务</p><h1>{store.merchant.name}</h1>
        <p className="icon-line"><MapPin size={17} />{store.merchant.region}</p><p className="lead">{store.merchant.description}</p></div>
      <div className="section-heading"><h2>服务项目</h2><span className="muted">共 {store.services.length} 项</span></div>
      {store.services.length === 0 ? <div className="commerce-card empty-state">商家还没有发布服务，请稍后再来。</div> :
        <div className="storefront-services">{store.services.map(service => <article className="commerce-card service-card" key={service.id}>
          <h2>{service.name}</h2><p className="service-description">{service.description}</p>
          <div className="service-meta"><strong>{money(service.price_fen)}</strong><span><Clock size={15} />{service.duration_minutes} 分钟</span></div>
          {service.availability_note && <p className="muted">{service.availability_note}</p>}
          <Link className="primary" to={`/stores/${store.merchant.id}/book/${service.id}`}>申请预约</Link>
        </article>)}</div>}
      <p className="storefront-note">预约申请需商家确认时间。当前不在线收款。</p>
    </>}
  </CommerceShell>
}
