import { useState, useEffect } from 'react'
import { Wifi, Plus, Trash2, RefreshCw } from 'lucide-react'
import { useAppStore } from '../store/appStore'

export function ChannelsPage() {
  const { channels, setChannels, toggleChannel, gatewayUrl } = useAppStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchChannels()
  }, [])

  const fetchChannels = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${gatewayUrl}/api/channels`)
      if (response.ok) {
        const data = await response.json()
        setChannels(data.channels || [])
      }
    } catch (error) {
      console.error('Failed to fetch channels:', error)
    } finally {
      setLoading(false)
    }
  }

  const channelTypes = [
    { type: 'telegram', name: 'Telegram', icon: '馃摫' },
    { type: 'discord', name: 'Discord', icon: '馃挰' },
    { type: 'slack', name: 'Slack', icon: '馃懃' },
    { type: 'whatsapp', name: 'WhatsApp', icon: '馃挱' },
    { type: 'matrix', name: 'Matrix', icon: '馃數' },
    { type: 'wechat', name: 'WeChat', icon: '馃挌' },
  ]

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-4">
        <h2 className="text-lg font-semibold mb-4">閫氶亾绠＄悊</h2>
        <nav className="space-y-1">
          <button
            onClick={() => window.history.back()}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <RefreshCw className="w-5 h-5" />
            <span>杩斿洖</span>
          </button>
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold">閫氶亾绠＄悊</h1>
            <button className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
              <Plus className="w-5 h-5" />
              娣诲姞閫氶亾
            </button>
          </div>

          {/* Channel Types */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold mb-4">鍙敤閫氶亾绫诲瀷</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {channelTypes.map((channel) => (
                <div
                  key={channel.type}
                  className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary-500 cursor-pointer transition-colors"
                >
                  <span className="text-2xl mb-2 block">{channel.icon}</span>
                  <span className="font-medium">{channel.name}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Active Channels */}
          <section>
            <h2 className="text-lg font-semibold mb-4">宸查厤缃€氶亾</h2>
            <div className="space-y-2">
              {loading ? (
                <div className="text-center py-8 text-gray-500">鍔犺浇涓?..</div>
              ) : channels.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Wifi className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p>鏆傛棤宸查厤缃殑閫氶亾</p>
                </div>
              ) : (
                channels.map((channel) => (
                  <div
                    key={channel.id}
                    className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex items-center gap-3">
                      <Wifi className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="font-medium">{channel.name}</p>
                        <p className="text-sm text-gray-500">{channel.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleChannel(channel.id)}
                        className={`px-3 py-1 rounded-full text-sm ${
                          channel.enabled
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {channel.enabled ? '宸插惎鐢? : '宸茬鐢?}
                      </button>
                      <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
