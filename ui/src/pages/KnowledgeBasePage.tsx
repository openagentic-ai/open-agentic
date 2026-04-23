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
      setStatusMessage(resp.error || '加载文档失败')
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
      setStatusMessage(resp.error || '上传失败')
      setLoading(false)
      return
    }
    setStatusMessage('上传成功，文档已入库并开始分块/嵌入。')
    setSelectedFile(null)
    setTitle('')
    await loadDocuments()
  }

  const onDelete = async (id: string) => {
    const resp = await api.knowledge.delete(id)
    if (!resp.success) {
      setStatusMessage(resp.error || '删除失败')
      return
    }
    setStatusMessage('文档已删除')
    await loadDocuments()
  }

  const onSearch = async () => {
    if (!query.trim()) return
    const resp = await api.knowledge.search(query.trim(), 5)
    if (!resp.success || !resp.data) {
      setStatusMessage(resp.error || '检索失败')
      return
    }
    setSearchResults(resp.data.results)
    setStatusMessage(`检索完成，返回 ${resp.data.results.length} 条结果`)
  }

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Database className="w-6 h-6 text-primary-600" />
          <h1 className="text-2xl font-semibold">知识库（MVP）</h1>
        </div>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">上传文档</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
              placeholder="文档标题（可选）"
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
              上传并处理
            </button>
          </div>
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">语义检索</h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
              placeholder="输入问题或关键词"
            />
            <button
              onClick={() => void onSearch()}
              disabled={!query.trim()}
              className="px-4 py-2 rounded bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 inline-flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              检索
            </button>
          </div>
          <div className="space-y-2">
            {searchResults.map((item, idx) => (
              <div key={`${item.document_id}-${idx}`} className="p-3 rounded border border-gray-200 dark:border-gray-700">
                <div className="text-sm font-medium">{item.title} · chunk #{item.chunk_index}</div>
                <div className="text-xs text-gray-500 mt-1">score: {item.score.toFixed(4)}</div>
                <p className="text-sm mt-2 whitespace-pre-wrap">{item.content}</p>
              </div>
            ))}
            {searchResults.length === 0 && <p className="text-sm text-gray-500">暂无检索结果</p>}
          </div>
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h2 className="font-medium">文档列表</h2>
          {loading ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="p-3 rounded border border-gray-200 dark:border-gray-700 flex items-start justify-between gap-4">
                  <div>
                    <div className="font-medium">{doc.title}</div>
                    <div className="text-sm text-gray-500">
                      {doc.filename} · {doc.status} · chunks: {doc.chunk_count} · {doc.size_bytes} bytes
                    </div>
                    {doc.error_message && <div className="text-sm text-red-500 mt-1">{doc.error_message}</div>}
                  </div>
                  <button
                    onClick={() => void onDelete(doc.id)}
                    className="px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 inline-flex items-center gap-1"
                  >
                    <Trash2 className="w-4 h-4" />
                    删除
                  </button>
                </div>
              ))}
              {documents.length === 0 && <p className="text-sm text-gray-500">暂无文档</p>}
            </div>
          )}
        </section>

        {statusMessage && <p className="text-sm text-gray-500">{statusMessage}</p>}
      </div>
    </div>
  )
}

