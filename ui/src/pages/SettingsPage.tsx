import { useEffect, useState } from 'react'
import { Settings as SettingsIcon, Key, Globe, Bell, Palette } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { useApi, type LlmProviderProfile } from '../lib/api'

export function SettingsPage() {
  const { darkMode, setDarkMode, gatewayUrl, setGatewayUrl } = useAppStore()
  const api = useApi()
  const [providers, setProviders] = useState<LlmProviderProfile[]>([])
  const [defaultModel, setDefaultModel] = useState('')
  const [drafts, setDrafts] = useState<Record<string, { apiBase: string; models: string; apiKey: string; enabled: boolean }>>({})
  const [loadingProviders, setLoadingProviders] = useState(false)
  const [savingProviderId, setSavingProviderId] = useState<string | null>(null)
  const [savingDefaultModel, setSavingDefaultModel] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')

  const loadProviderSettings = async () => {
    setLoadingProviders(true)
    const resp = await api.llm.getProviders()
    if (!resp.success || !resp.data) {
      setStatusMessage(resp.error || '加载模型配置失败')
      setLoadingProviders(false)
      return
    }
    const data = resp.data
    setProviders(data.profiles)
    setDefaultModel(data.default_model)
    const nextDrafts: Record<string, { apiBase: string; models: string; apiKey: string; enabled: boolean }> = {}
    data.profiles.forEach((p) => {
      nextDrafts[p.id] = {
        apiBase: p.api_base || '',
        models: (p.models || []).join(', '),
        apiKey: '',
        enabled: p.enabled,
      }
    })
    setDrafts(nextDrafts)
    setStatusMessage('')
    setLoadingProviders(false)
  }

  useEffect(() => {
    void loadProviderSettings()
  }, [])

  const saveProvider = async (providerId: string) => {
    const draft = drafts[providerId]
    if (!draft) return
    setSavingProviderId(providerId)
    const models = draft.models
      .split(',')
      .map((m) => m.trim())
      .filter((m) => m.length > 0)
    const resp = await api.llm.updateProvider(providerId, {
      api_base: draft.apiBase,
      api_key: draft.apiKey || undefined,
      models,
      enabled: draft.enabled,
    })
    if (!resp.success) {
      setStatusMessage(resp.error || `保存 ${providerId} 失败`)
      setSavingProviderId(null)
      return
    }
    setStatusMessage(`已保存 ${providerId} 配置`)
    await loadProviderSettings()
    setSavingProviderId(null)
  }

  const saveDefaultModel = async () => {
    if (!defaultModel.trim()) return
    setSavingDefaultModel(true)
    const resp = await api.llm.setDefaultModel(defaultModel.trim())
    if (!resp.success) {
      setStatusMessage(resp.error || '保存默认模型失败')
      setSavingDefaultModel(false)
      return
    }
    setStatusMessage('默认模型已更新')
    await loadProviderSettings()
    setSavingDefaultModel(false)
  }

  const sections = [
    { id: 'general', icon: SettingsIcon, label: '通用' },
    { id: 'api', icon: Key, label: 'API 密钥' },
    { id: 'gateway', icon: Globe, label: '网关' },
    { id: 'notifications', icon: Bell, label: '通知' },
    { id: 'appearance', icon: Palette, label: '外观' },
  ]

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-4">
        <h2 className="text-lg font-semibold mb-4">设置</h2>
        <nav className="space-y-1">
          {sections.map((section) => (
            <button
              key={section.id}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <section.icon className="w-5 h-5" />
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-2xl mx-auto space-y-8">
          {/* Gateway URL */}
          <section>
            <h3 className="text-lg font-semibold mb-4">网关设置</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Gateway URL</label>
                <input
                  type="text"
                  value={gatewayUrl}
                  onChange={(e) => setGatewayUrl(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                  placeholder="http://localhost:18789"
                />
              </div>
            </div>
          </section>

          {/* Appearance */}
          <section>
            <h3 className="text-lg font-semibold mb-4">外观</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span>深色模式</span>
                <button
                  onClick={() => setDarkMode(!darkMode)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    darkMode ? 'bg-primary-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      darkMode ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </section>

          {/* API Keys */}
          <section>
            <h3 className="text-lg font-semibold mb-4">模型供应商与 API</h3>
            {loadingProviders ? (
              <p className="text-sm text-gray-500">正在加载模型配置...</p>
            ) : (
              <div className="space-y-6">
                <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700">
                  <label className="block text-sm font-medium mb-2">默认模型（global）</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={defaultModel}
                      onChange={(e) => setDefaultModel(e.target.value)}
                      className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                      placeholder="deepseek/deepseek-chat"
                    />
                    <button
                      onClick={() => void saveDefaultModel()}
                      disabled={savingDefaultModel}
                      className="px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60"
                    >
                      保存
                    </button>
                  </div>
                </div>

                {providers.map((provider) => {
                  const draft = drafts[provider.id]
                  if (!draft) return null
                  return (
                    <div key={provider.id} className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium">{provider.display_name}</h4>
                          <p className="text-xs text-gray-500">{provider.id}</p>
                        </div>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={draft.enabled}
                            onChange={(e) =>
                              setDrafts((prev) => ({
                                ...prev,
                                [provider.id]: { ...prev[provider.id], enabled: e.target.checked },
                              }))
                            }
                          />
                          启用
                        </label>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1">API Base</label>
                        <input
                          type="text"
                          value={draft.apiBase}
                          onChange={(e) =>
                            setDrafts((prev) => ({
                              ...prev,
                              [provider.id]: { ...prev[provider.id], apiBase: e.target.value },
                            }))
                          }
                          className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1">API Key（留空表示不修改）</label>
                        <input
                          type="password"
                          value={draft.apiKey}
                          onChange={(e) =>
                            setDrafts((prev) => ({
                              ...prev,
                              [provider.id]: { ...prev[provider.id], apiKey: e.target.value },
                            }))
                          }
                          className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                          placeholder={provider.api_key_configured ? provider.api_key_masked || '已配置' : 'sk-...'}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1">模型列表（逗号分隔）</label>
                        <input
                          type="text"
                          value={draft.models}
                          onChange={(e) =>
                            setDrafts((prev) => ({
                              ...prev,
                              [provider.id]: { ...prev[provider.id], models: e.target.value },
                            }))
                          }
                          className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700"
                          placeholder="openai/gpt-4.1-mini, openai/gpt-4.1"
                        />
                      </div>

                      <div className="flex justify-end">
                        <button
                          onClick={() => void saveProvider(provider.id)}
                          disabled={savingProviderId === provider.id}
                          className="px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60"
                        >
                          保存 {provider.display_name}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            {statusMessage && <p className="mt-3 text-sm text-gray-500">{statusMessage}</p>}
          </section>
        </div>
      </div>
    </div>
  )
}
