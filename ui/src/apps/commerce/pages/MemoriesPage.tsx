import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Search, Plus, ArrowUpRight } from 'lucide-react'
import { LoginGate, Field } from '../components/CommerceShell'
import { commerceRequest } from '../lib/commerce'

interface VaultNote { path: string; name: string; content: string; links: string[]; properties: Record<string, unknown> }
interface Detail extends VaultNote { backlinks: { path: string; name: string }[]; uri: string }

function MemoriesWorkspace() {
  const [notes, setNotes] = useState<VaultNote[]>([])
  const [selected, setSelected] = useState<Detail | null>(null)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [vaultPath, setVaultPath] = useState('')
  async function load(search = query) {
    setLoading(true); setError('')
    try { setNotes(await commerceRequest<VaultNote[]>(`/api/memory/vault/search?q=${encodeURIComponent(search)}`)) }
    catch (e) { setError(e instanceof Error ? e.message : '检索失败') }
    finally { setLoading(false) }
  }
  useEffect(() => {
    let alive = true
    Promise.all([
      commerceRequest<VaultNote[]>('/api/memory/vault/search'),
      commerceRequest<{ path: string }>('/api/memory/vault'),
    ]).then(([items, status]) => { if (alive) { setNotes(items); setVaultPath(status.path) } })
      .catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])
  async function open(path: string) {
    setError('')
    try { setSelected(await commerceRequest<Detail>(`/api/memory/vault/note?path=${encodeURIComponent(path)}`)); setCreating(false) }
    catch (e) { setError(e instanceof Error ? e.message : '读取失败') }
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('')
    const form = new FormData(e.currentTarget)
    try {
      await commerceRequest('/api/memory/procedures', { method: 'POST', body: JSON.stringify({
        name: form.get('name'), description: form.get('description'), trigger_pattern: form.get('trigger'),
        steps: String(form.get('steps')).split('\n').map(s => s.trim()).filter(Boolean),
      }) })
      setCreating(false); setSelected(null); setQuery(''); await load('')
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { setBusy(false) }
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">MEMORY / 第四层</p><h1>把经验变成可复用的流程。</h1><p className="lead">用 Obsidian 兼容的 Markdown、属性与双向链接，组织你的程序性记忆。</p></div>
      <button className="primary" onClick={() => { setCreating(true); setSelected(null) }}><Plus size={17} />记录流程</button></div>
    <div className="memory-tiers"><span>01 工作记忆</span><span>02 核心记忆</span><span>03 情节记忆</span><strong>04 程序性记忆 · Vault</strong></div>
    {error && <p role="alert" className="commerce-error">{error}</p>}
    <div className="workspace-grid">
      <aside className="commerce-card"><form className="search-form" onSubmit={e => { e.preventDefault(); void load() }}><input aria-label="搜索流程" placeholder="搜索流程…" value={query} onChange={e => setQuery(e.target.value)} /><button className="quiet" aria-label="搜索"><Search size={18} /></button></form>
        {loading ? <p role="status">正在检索…</p> : notes.length ? <div className="note-list">{notes.map(note => <button className={`note-item ${selected?.path === note.path ? 'active' : ''}`} key={note.path} onClick={() => open(note.path)}><BookOpen size={16} /><span>{note.name}<small>{note.path}</small></span></button>)}</div> : <p className="muted">还没有匹配的流程。</p>}
        <div className="share-block"><h3>Obsidian Vault</h3><p className="muted">可以在部署机器上，用 Obsidian 打开这个目录编辑流程。</p><code className="vault-path">{vaultPath}</code><p className="muted">远程部署时，需要将 Vault 同步到自己的设备。此版本不自动同步或调用桌面插件。</p></div>
        <Link className="quiet" to="/merchants">返回商家工作台</Link>
      </aside>
      <section>
        {creating ? <form className="commerce-card editor" onSubmit={save}><h2>记录可复用流程</h2>
          <Field label="流程名称"><input name="name" required maxLength={128} placeholder="例如：服务接单流程" /></Field>
          <Field label="流程说明"><textarea name="description" required maxLength={3000} rows={2} /></Field>
          <Field label="触发关键词"><input name="trigger" maxLength={200} placeholder="例如：接单、预约" /></Field>
          <Field label="执行步骤" hint="每行一个步骤；可以用 [[相关流程]] 关联笔记"><textarea name="steps" required maxLength={10000} rows={6} /></Field>
          <div className="actions"><button className="primary" disabled={busy}>{busy ? '保存中…' : '保存流程'}</button><button type="button" className="quiet" disabled={busy} onClick={() => setCreating(false)}>取消</button></div>
        </form> : selected ? <article className="commerce-card note-detail"><p className="eyebrow">{selected.path}</p><h2>{selected.name}</h2><pre>{selected.content}</pre>
          <h3>笔记属性</h3><dl>{Object.entries(selected.properties).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl>
          <h3>链接到</h3><p className="muted">{selected.links.length ? selected.links.join(' · ') : '暂无双向链接'}</p>
          <h3>反向链接</h3>{selected.backlinks.length ? selected.backlinks.map(note => <button className="quiet" key={note.path} onClick={() => open(note.path)}>{note.name}</button>) : <p className="muted">暂无引用此笔记的流程</p>}
          <a className="secondary" href={selected.uri}>在同机 Obsidian 中打开<ArrowUpRight size={15} /></a>
        </article> : <div className="commerce-card empty-state"><BookOpen size={30} /><h2>记录一次，反复使用</h2><p>保存服务流程、接单步骤和常用操作。Agent 检索会按当前用户读取相关流程。</p><button className="secondary" onClick={() => setCreating(true)}>记录第一个流程</button></div>}
      </section>
    </div>
  </>
}

export function MemoriesPage() { return <LoginGate><MemoriesWorkspace /></LoginGate> }
