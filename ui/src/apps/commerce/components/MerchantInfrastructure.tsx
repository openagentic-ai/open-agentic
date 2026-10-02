import { useState, type FormEvent } from 'react'
import { Field } from './CommerceShell'
import { commerceRequest } from '../lib/commerce'
export function MerchantInfrastructure({ merchantId, imported }: { merchantId: string; imported: () => Promise<void> }) {
  const [origin, setOrigin] = useState(window.location.origin); const [share, setShare] = useState<{ url: string; svg: string } | null>(null)
  const [catalog, setCatalog] = useState(''); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false)
  async function qr(event: FormEvent) { event.preventDefault(); setBusy(true); setError(''); try { setShare(await commerceRequest(`/api/merchants/${merchantId}/share?origin=${encodeURIComponent(origin)}`)) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  async function example() { setError(''); try { const data = await commerceRequest<{ catalog: unknown }>('/api/commerce/integrations/example', {}, false); setCatalog(JSON.stringify(data.catalog, null, 2)) } catch (e) { setError((e as Error).message) } }
  async function upload(event: FormEvent) { event.preventDefault(); setBusy(true); setError(''); setNotice(''); try { const parsed = JSON.parse(catalog); const result = await commerceRequest<{ count: number }>(`/api/merchants/${merchantId}/integrations/catalog`, { method: 'POST', body: JSON.stringify(parsed) }); await imported(); setNotice(`已导入 ${result.count} 项服务。示例默认为草稿，发布后才对客户开放。`) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  return <div className="share-block">
    <h3>店铺二维码</h3><form onSubmit={qr}><Field label="站点地址" hint="手机扫码需要能访问这个地址。127.0.0.1 只适合在当前电脑使用。"><input type="url" value={origin} maxLength={100} onChange={e => setOrigin(e.target.value)} required /></Field><button className="secondary" disabled={busy}>生成二维码</button></form>
    {share && <div><img className="store-qr" src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(share.svg)}`} alt="店铺二维码" /><p className="muted">{share.url}</p><a className="quiet" download={`store-${merchantId}.svg`} href={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(share.svg)}`}>下载二维码</a></div>}
    <details><summary>导入 SaaS 服务目录</summary><p className="muted">使用开放目录格式导入；相同系统和外部编号会更新已有服务。</p><button className="quiet" type="button" onClick={example}>填入本地示例</button><form onSubmit={upload}><Field label="目录 JSON"><textarea rows={10} required value={catalog} onChange={e => setCatalog(e.target.value)} /></Field><button className="secondary" disabled={busy}>导入目录</button></form></details>
    {notice && <p role="status" className="commerce-notice">{notice}</p>}{error && <p role="alert" className="commerce-error">{error}</p>}
  </div>
}

interface Delivery { id: string; order_id: string; system: string; status: string; attempts: number; error: string }
export function IntegrationDeliveries({ merchantId }: { merchantId: string }) {
  const [items, setItems] = useState<Delivery[]>([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function refresh() { setBusy(true); setError(''); try { setItems(await commerceRequest<Delivery[]>(`/api/merchants/${merchantId}/integrations/deliveries`)) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  async function retry(id: string) { setBusy(true); setError(''); try { await commerceRequest(`/api/merchants/${merchantId}/integrations/deliveries/${id}/retry`,{method:'POST'}); await refresh() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  return <section className="commerce-card"><div className="section-heading"><h2>商家系统投递记录</h2><button className="secondary" disabled={busy} onClick={refresh}>加载记录</button></div><p className="muted">本地示例用于验证接入和重试。投递成功只表示对方收到，不会自动更改履约状态。</p>{error && <p className="commerce-error" role="alert">{error}</p>}{items.map(item=><div className="case-record" key={item.id}><p>{item.order_id} · {item.system}</p><p>{item.status==='delivered'?'已投递':item.status==='failed'?'投递失败':'待投递'} · 尝试 {item.attempts} 次</p>{item.error&&<p>{item.error}</p>}<button className="quiet" disabled={busy || item.status==='delivered'} onClick={()=>retry(item.id)}>执行或重试</button></div>)}</section>
}
