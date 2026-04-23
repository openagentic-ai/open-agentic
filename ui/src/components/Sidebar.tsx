import { useLocation, useNavigate } from 'react-router-dom'
import { 
  MessageSquare, 
  Settings, 
  Wifi, 
  Users, 
  Hash,
  Bot,
  X,
  Layout,
  Smartphone,
  Puzzle,
  Database
} from 'lucide-react'
import { useAppStore } from '../store/appStore'

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { sidebarOpen, setSidebarOpen, channels, darkMode, setDarkMode } = useAppStore()

  const navItems = [
    { path: '/', icon: MessageSquare, label: '瀵硅瘽' },
    { path: '/canvas', icon: Layout, label: '鐢诲竷' },
    { path: '/devices', icon: Smartphone, label: '璁惧' },
    { path: '/skills', icon: Puzzle, label: '鎶€鑳? },
    { path: '/channels', icon: Wifi, label: '閫氶亾' },
    { path: '/sessions', icon: Users, label: '浼氳瘽' },
    { path: '/knowledge', icon: Database, label: '鐭ヨ瘑搴? },
    { path: '/settings', icon: Settings, label: '璁剧疆' },
  ]

  if (!sidebarOpen) return null

  return (
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Bot className="w-6 h-6 text-primary-600" />
          <span className="font-bold text-lg">OpenAgentic</span>
        </div>
        <button 
          onClick={() => setSidebarOpen(false)}
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                isActive 
                  ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300' 
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Channels */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2 px-3">
          娲昏穬閫氶亾
        </h3>
        <div className="space-y-1">
          {channels.slice(0, 5).map((channel) => (
            <div 
              key={channel.id}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300"
            >
              <Hash className="w-4 h-4 text-gray-400" />
              <span>{channel.name}</span>
              {channel.enabled && (
                <span className="w-2 h-2 bg-green-500 rounded-full ml-auto" />
              )}
            </div>
          ))}
          {channels.length === 0 && (
            <p className="text-sm text-gray-400 px-3">鏆傛棤娲昏穬閫氶亾</p>
          )}
        </div>
      </div>

      {/* Theme Toggle */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="w-full flex items-center justify-between px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
        >
          <span>{darkMode ? '馃寵 娣辫壊妯″紡' : '鈽€锔?娴呰壊妯″紡'}</span>
        </button>
      </div>
    </aside>
  )
}
