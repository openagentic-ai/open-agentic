import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ArrowUpRight, Check, MapPin, Clock, Pencil } from 'lucide-react'
import { LoginGate, Field } from '../components/CommerceShell'
import { MerchantInfrastructure, IntegrationDeliveries } from '../components/MerchantInfrastructure'
import { OrdersPanel } from '../components/OrdersPanel'
import { commerceRequest, money, serviceInput, type Merchant, type MerchantInput, type Service, type ServiceInput } from '../lib/commerce'

const emptyMerchant: MerchantInput = { name: '', region: '', description: '', contact_name: '', contact_phone: '' }

function MerchantForm({ value, save, cancel }: { value?: Merchant; save: (data: MerchantInput) => Promise<void>; cancel: () => void }) {
  const [data, setData] = useState<MerchantInput>(value || emptyMerchant)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const change = (key: keyof MerchantInput, value: string) => setData({ ...data, [key]: value })
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const { name, region, description, contact_name, contact_phone } = data
      await save({ name, region, description, contact_name, contact_phone })
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { setBusy(false) }
  }
  return <form className="commerce-card editor" onSubmit={submit}>
    <h2>{value ? '编辑店铺资料' : '开通一家店铺'}</h2>
    <div className="form-grid">
      <Field label="店铺名称"><input required maxLength={100} value={data.name} onChange={e => change('name', e.target.value)} placeholder="例如：城南家电维修" /></Field>
      <Field label="服务区域"><input required maxLength={100} value={data.region} onChange={e => change('region', e.target.value)} placeholder="例如：杭州 · 西湖区" /></Field>
      <Field label="经营联系人"><input required maxLength={100} value={data.contact_name} onChange={e => change('contact_name', e.target.value)} /></Field>
      <Field label="联系电话" hint="仅工作台可见"><input required type="tel" maxLength={32} value={data.contact_phone} onChange={e => change('contact_phone', e.target.value)} /></Field>
    </div>
    <Field label="店铺介绍"><textarea maxLength={3000} rows={3} value={data.description} onChange={e => change('description', e.target.value)} /></Field>
    {error && <p role="alert" className="commerce-error">{error}</p>}
    <div className="actions"><button disabled={busy} className="primary">{busy ? '保存中…' : '保存店铺'}</button><button disabled={busy} className="quiet" type="button" onClick={cancel}>取消</button></div>
  </form>
}

function ServiceForm({ value, save, cancel }: { value?: Service; save: (data: ServiceInput) => Promise<void>; cancel: () => void }) {
  const [name, setName] = useState(value?.name || '')
  const [description, setDescription] = useState(value?.description || '')
  const [price, setPrice] = useState(value ? String(value.price_fen / 100) : '')
  const [duration, setDuration] = useState(value?.duration_minutes || 60)
  const [availability, setAvailability] = useState(value?.availability_note || '')
  const [published, setPublished] = useState(value?.is_published || false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try { await save({ name, description, price_fen: Math.round(Number(price) * 100), duration_minutes: duration,
      availability_note: availability, is_published: published }) }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { setBusy(false) }
  }
  return <form className="commerce-card editor" onSubmit={submit}>
    <h2>{value ? '编辑服务' : '新增服务'}</h2>
    <Field label="服务名称"><input required maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="例如：空调清洗" /></Field>
    <div className="form-grid">
      <Field label="价格（元）"><input required type="number" min="0" max="1000000" step="0.01" value={price} onChange={e => setPrice(e.target.value)} /></Field>
      <Field label="服务时长（分钟）"><input required type="number" min="1" max="10080" value={duration} onChange={e => setDuration(Number(e.target.value))} /></Field>
    </div>
    <Field label="服务说明"><textarea maxLength={3000} rows={3} value={description} onChange={e => setDescription(e.target.value)} /></Field>
    <Field label="营业时间或服务安排" hint="供客户参考，实际服务时间由商家接单确认"><input maxLength={500} value={availability} onChange={e => setAvailability(e.target.value)} placeholder="例如：周一至周六 09:00—18:00" /></Field>
    <label className="checkbox-field"><input type="checkbox" checked={published} onChange={e => setPublished(e.target.checked)} />发布到店铺，允许客户查看</label>
    {error && <p role="alert" className="commerce-error">{error}</p>}
    <div className="actions"><button className="primary" disabled={busy}>{busy ? '保存中…' : published ? '保存并发布' : '保存草稿'}</button><button type="button" className="quiet" disabled={busy} onClick={cancel}>取消</button></div>
  </form>
}

function Workspace() {
  const [merchants, setMerchants] = useState<Merchant[]>([])
  const [selected, setSelected] = useState('')
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [servicesLoading, setServicesLoading] = useState(false)
  const [error, setError] = useState('')
  const [storeForm, setStoreForm] = useState<'create' | 'edit' | null>(null)
  const [serviceForm, setServiceForm] = useState<Service | 'new' | null>(null)
  const [notice, setNotice] = useState('')
  const [busyService, setBusyService] = useState('')
  const merchant = merchants.find(m => m.id === selected)
  useEffect(() => {
    let alive = true
    commerceRequest<Merchant[]>('/api/merchants').then(items => {
      if (alive) { setMerchants(items); setSelected(items[0]?.id || '') }
    }).catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])
  useEffect(() => {
    let alive = true
    setServices([]); setServiceForm(null); setNotice('')
    if (!selected) return
    setServicesLoading(true); setError('')
    commerceRequest<Service[]>(`/api/merchants/${selected}/services`).then(items => { if (alive) setServices(items) })
      .catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setServicesLoading(false) })
    return () => { alive = false }
  }, [selected])
  async function saveMerchant(data: MerchantInput) {
    const editing = storeForm === 'edit'
    const item = await commerceRequest<Merchant>(`/api/merchants${editing ? `/${selected}` : ''}`, {
      method: editing ? 'PUT' : 'POST', body: JSON.stringify(data),
    })
    setMerchants(old => editing ? old.map(m => m.id === item.id ? item : m) : [item, ...old])
    setSelected(item.id); setStoreForm(null); setNotice('店铺资料已保存')
  }
  async function saveService(data: ServiceInput, id?: string) {
    const item = await commerceRequest<Service>(`/api/merchants/${selected}/services${id ? `/${id}` : ''}`, {
      method: id ? 'PUT' : 'POST', body: JSON.stringify(data),
    })
    setServices(old => id ? old.map(s => s.id === id ? item : s) : [item, ...old])
    setServiceForm(null); setNotice(item.is_published ? '服务已发布，客户可以查看' : '服务已保存为草稿')
  }
  async function toggle(item: Service) {
    setBusyService(item.id); setError('')
    try { await saveService({ ...serviceInput(item), is_published: !item.is_published }, item.id) }
    catch (e) { setError(e instanceof Error ? e.message : '更新失败') }
    finally { setBusyService('') }
  }
  const link = merchant ? `${window.location.origin}/stores/${merchant.id}` : ''
  return <>
    <div className="page-heading"><div><p className="eyebrow">WORKSPACE / 商家工作台</p><h1>让服务被看见。</h1><p className="lead">管理店铺和服务，把你的店铺分享给客户。</p></div>
      <button className="primary" disabled={loading} onClick={() => { setStoreForm('create'); setServiceForm(null) }}><Plus size={17} />开通店铺</button></div>
    {error && <div className="commerce-error" role="alert">{error}<button className="quiet" onClick={() => window.location.reload()}>重新加载</button></div>}
    {notice && <p role="status" className="commerce-notice"><Check size={16} />{notice}</p>}
    {loading ? <p role="status">正在加载店铺…</p> : <>
      {storeForm && <MerchantForm key={`${storeForm}-${selected}`} value={storeForm === 'edit' ? merchant : undefined} save={saveMerchant} cancel={() => setStoreForm(null)} />}
      {!merchant && !storeForm && !error && <div className="commerce-card empty-state"><h2>从第一家店铺开始</h2><p>填写店铺名称和服务区域，再发布你的第一项服务。</p><button className="primary" onClick={() => setStoreForm('create')}>开通我的店铺</button></div>}
      {merchant && <>
        <div className="workspace-grid">
          <aside className="commerce-card store-summary">
            <p className="eyebrow">我的店铺</p>
            <Field label="选择店铺"><select value={selected} disabled={!!storeForm || !!serviceForm || !!busyService} onChange={e => setSelected(e.target.value)}>{merchants.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
            <h2>{merchant.name}</h2><p className="muted icon-line"><MapPin size={15} />{merchant.region}</p><p>{merchant.description || '添加店铺介绍，让客户更了解你。'}</p>
            <button className="secondary" onClick={() => { setStoreForm('edit'); setServiceForm(null) }}><Pencil size={15} />编辑店铺资料</button>
            <div className="share-block"><h3>客户入口</h3><p className="muted">分享店铺链接，让客户查看已发布服务。</p>
              <input aria-label="店铺分享链接" readOnly value={link} onFocus={e => e.target.select()} />
              <div className="actions"><button className="quiet" onClick={async () => { try { await navigator.clipboard.writeText(link); setNotice('店铺链接已复制') } catch { setNotice('请选中上方链接并复制') } }}>复制链接</button>
                <Link className="quiet" to={`/stores/${selected}`} target="_blank" rel="noreferrer">查看店铺<ArrowUpRight size={15} /></Link></div>
            </div>
            <MerchantInfrastructure key={selected} merchantId={selected} imported={async () => { setServices(await commerceRequest<Service[]>(`/api/merchants/${selected}/services`)) }} />
          </aside>
          <section><div className="section-heading"><div><h2>服务目录 <span className="count">{services.length}</span></h2><p className="muted">草稿仅自己可见，发布后客户可查看。</p></div><button className="secondary" onClick={() => { setServiceForm('new'); setStoreForm(null) }}><Plus size={16} />新增服务</button></div>
            {serviceForm && <ServiceForm key={serviceForm === 'new' ? 'new' : serviceForm.id} value={serviceForm === 'new' ? undefined : serviceForm} save={data => saveService(data, serviceForm === 'new' ? undefined : serviceForm?.id)} cancel={() => setServiceForm(null)} />}
            {servicesLoading ? <p role="status">正在加载服务…</p> : services.length === 0 ? <div className="commerce-card empty-state"><h3>还没有服务</h3><p>新增服务，填写价格、时长和服务说明。</p></div> :
              <div className="service-list">{services.map(item => <article className="commerce-card service-card" key={item.id}>
                <div className="section-heading"><h3>{item.name}</h3><span className={`badge ${item.is_published ? 'published' : ''}`}>{item.is_published ? '已发布' : '草稿'}</span></div>
                <p className="muted service-description">{item.description || '暂无服务说明'}</p><div className="service-meta"><strong>{money(item.price_fen)}</strong><span><Clock size={14} />{item.duration_minutes} 分钟</span></div>
                {item.availability_note && <p className="muted">{item.availability_note}</p>}
                <div className="actions"><button className="quiet" disabled={!!busyService} onClick={() => { setServiceForm(item); setStoreForm(null) }}>编辑</button><button className="quiet" disabled={!!busyService} onClick={() => toggle(item)}>{busyService === item.id ? '更新中…' : item.is_published ? '下架' : '发布'}</button></div>
              </article>)}</div>}
            <OrdersPanel key={selected} merchantId={selected} />
            <IntegrationDeliveries key={`deliveries-${selected}`} merchantId={selected} />
          </section>
        </div>
      </>}
    </>}
  </>
}

export function MerchantsPage() { return <LoginGate><Workspace /></LoginGate> }
