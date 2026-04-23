import { useEffect, useState } from 'react'
import { Database, Upload, Search, Trash2 } from 'lucide-react'
import { useApi, type KnowledgeDocument, type KnowledgeSearchResult } from '../lib/api'

export function KnowledgeBasePage() {
  const api = useApi()
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([])
  const [query, setQuery] = useState('')
  const [title, setTitle] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')

  const loadDocuments = async () => {
    setLoading(true)
    const resp = await api.knowledge.list(200)
    if (!resp.success || !resp.data) {
      setStatusMessage(resp.error || '鍔犺浇鏂囨。澶辫触')
      setLoading(false)
      return
    }
    setDocuments(resp.data)
    setLoading(false)
  }

  useEffect(() => {
    void loadDocuments()
  }, [])

  const onUpload = async () => {
    if (!selectedFile) return
    setLoading(true)
    const resp = await api.knowledge.upload(selectedFile, title)
    if (!resp.success) {
      setStatusMessage(resp.error || '涓婁紶澶辫触')
      setLoading(false)
      return
    }
    setStatusMessage('涓婁紶鎴愬姛锛屾枃妗ｅ凡鍏ュ簱骞跺紑濮嬪垎鍧?宓屽叆銆?)
    setSelectedFile(null)
    setTitle('')
    await loadDocuments()
  }

  const onDelete = async (id: string) => {
    const resp = await api.knowledge.delete(id)
    if (!resp.success) {
      setStatusMessage(resp.error || '鍒犻櫎澶辫触')
      return
    }
    setStatusMessage('鏂囨。宸插垹闄?)
    await loadDocuments()
  }

  const onSearch = async () => {
    if (!query.trim()) return
    const resp = await api.knowledge.search(query.trim(), 5)
    if (!resp.success || !resp.data) {
      setStatusMessage(resp.error || '妫€绱㈠け璐?)
      return
    }
    setSearchResults(resp.data.results)
    setStatusMessage(`妫€绱㈠畬鎴愶紝杩斿洖 ${resp.data.results.length} 鏉＄粨鏋渀)
  }

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Database className="w-6 h-6 text-primary-600" />
          <h1 className="text-2xl font-semibold">鐭ヨ瘑搴擄紙MVP锛?/h1>
        </div>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">涓婁紶鏂囨。</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
              placeholder="鏂囨。鏍囬锛堝彲閫夛級"
            />
            <input
              type="file"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
            />
            <button
              onClick={() => void onUpload()}
              disabled={!selectedFile || loading}
              className="px-4 py-2 rounded bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 inline-flex items-center justify-center gap-2"
            >
              <Upload className="w-4 h-4" />
              涓婁紶骞跺鐞?            </button>
          </div>
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">璇箟妫€绱?/h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
              placeholder="杈撳叆闂鎴栧叧閿瘝"
            />
            <button
              onClick={() => void onSearch()}
              disabled={!query.trim()}
              className="px-4 py-2 rounded bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 inline-flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              妫€绱?            </button>
          </div>
          <div className="space-y-2">
            {searchResults.map((item, idx) => (
              <div key={`${item.document_id}-${idx}`} className="p-3 rounded border border-gray-200 dark:border-gray-700">
                <div className="text-sm font-medium">{item.title} 路 chunk #{item.chunk_index}</div>
                <div className="text-xs text-gray-500 mt-1">score: {item.score.toFixed(4)}</div>
                <p className="text-sm mt-2 whitespace-pre-wrap">{item.content}</p>
              </div>
            ))}
            {searchResults.length === 0 && <p className="text-sm text-gray-500">鏆傛棤妫€绱㈢粨鏋?/p>}
          </div>
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">鏂囨。鍒楄〃</h2>
          {loading ? (
            <p className="text-sm text-gray-500">鍔犺浇涓?..</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="p-3 rounded border border-gray-200 dark:border-gray-700 flex items-start justify-between gap-4">
                  <div>
                    <div className="font-medium">{doc.title}</div>
                    <div className="text-sm text-gray-500">
                      {doc.filename} 路 {doc.status} 路 chunks: {doc.chunk_count} 路 {doc.size_bytes} bytes
                    </div>
                    {doc.error_message && <div className="text-sm text-red-500 mt-1">{doc.error_message}</div>}
                  </div>
                  <button
                    onClick={() => void onDelete(doc.id)}
                    className="px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 inline-flex items-center gap-1"
                  >
                    <Trash2 className="w-4 h-4" />
                    鍒犻櫎
                  </button>
                </div>
              ))}
              {documents.length === 0 && <p className="text-sm text-gray-500">鏆傛棤鏂囨。</p>}
            </div>
          )}
        </section>

        {statusMessage && <p className="text-sm text-gray-500">{statusMessage}</p>}
      </div>
    </div>
  )
}

