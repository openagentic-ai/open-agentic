import { useState } from 'react'

export interface Skill {
  id: string
  name: string
  description: string
  version: string
  author?: string
  category: string
  tags: string[]
  enabled: boolean
  source: 'bundled' | 'managed' | 'workspace' | 'clawhub'
}

export function SkillsPage() {
  const [activeTab, setActiveTab] = useState<'bundled' | 'managed' | 'workspace' | 'clawhub'>('bundled')
  const [skills, setSkills] = useState<Skill[]>([
    { id: 'builtin.file_ops', name: '鏂囦欢鎿嶄綔', description: '璇诲彇銆佸啓鍏ャ€佸鍒躲€佺Щ鍔ㄦ枃浠跺拰鐩綍', version: '1.0.0', author: 'OpenAgentic', category: 'Productivity', tags: ['鏂囦欢', 'IO'], enabled: true, source: 'bundled' },
    { id: 'builtin.web_search', name: '缃戦〉鎼滅储', description: '浣跨敤鎼滅储寮曟搸鏌ユ壘淇℃伅', version: '1.0.0', author: 'OpenAgentic', category: 'Analysis', tags: ['鎼滅储', '缃戠粶'], enabled: true, source: 'bundled' },
    { id: 'builtin.image_gen', name: '鍥惧儚鐢熸垚', description: '浣跨敤 AI 鐢熸垚鍥惧儚', version: '1.0.0', author: 'OpenAgentic', category: 'Media', tags: ['鍥惧儚', 'AI', '鐢熸垚'], enabled: true, source: 'bundled' },
    { id: 'builtin.code_analyze', name: '浠ｇ爜鍒嗘瀽', description: '鍒嗘瀽浠ｇ爜缁撴瀯銆佹娴嬮棶棰樸€佷紭鍖栧缓璁?, version: '1.0.0', author: 'OpenAgentic', category: 'Development', tags: ['浠ｇ爜', '鍒嗘瀽', '寮€鍙?], enabled: true, source: 'bundled' },
    { id: 'builtin.data_process', name: '鏁版嵁澶勭悊', description: '澶勭悊鍜屽垎鏋愮粨鏋勫寲鏁版嵁', version: '1.0.0', author: 'OpenAgentic', category: 'Analysis', tags: ['鏁版嵁', '澶勭悊'], enabled: true, source: 'bundled' },
    { id: 'builtin.automation', name: '鑷姩鍖栦换鍔?, description: '鍒涘缓鍜屾墽琛岃嚜鍔ㄥ寲宸ヤ綔娴?, version: '1.0.0', author: 'OpenAgentic', category: 'Automation', tags: ['鑷姩鍖?, '宸ヤ綔娴?], enabled: true, source: 'bundled' },
    { id: 'builtin.safe_execute', name: '瀹夊叏鎵ц', description: '鍦ㄦ矙绠辩幆澧冧腑瀹夊叏鎵ц浠ｇ爜', version: '1.0.0', author: 'OpenAgentic', category: 'Security', tags: ['瀹夊叏', '娌欑'], enabled: true, source: 'bundled' },
  ])

  const [clawhubSkills] = useState<Skill[]>([
    { id: 'clawhub.web_scraper', name: '缃戦〉鎶撳彇', description: '楂樻晥鎶撳彇缃戦〉鍐呭', version: '1.2.0', author: 'Community', category: 'Utility', tags: ['鐖櫕', '缃戦〉'], enabled: false, source: 'clawhub' },
    { id: 'clawhub.pdf_tool', name: 'PDF 宸ュ叿', description: 'PDF 鍒涘缓銆佺紪杈戝拰杞崲', version: '2.0.1', author: 'Community', category: 'Utility', tags: ['PDF', '鏂囨。'], enabled: false, source: 'clawhub' },
    { id: 'clawhub.ocr', name: 'OCR 鏂囧瓧璇嗗埆', description: '浠庡浘鍍忎腑鎻愬彇鏂囧瓧', version: '1.5.0', author: 'Community', category: 'Utility', tags: ['OCR', '鏂囧瓧璇嗗埆'], enabled: false, source: 'clawhub' },
  ])

  const toggleSkill = (skillId: string) => {
    setSkills(prev => prev.map(skill => 
      skill.id === skillId ? { ...skill, enabled: !skill.enabled } : skill
    ))
  }

  const installSkill = (skill: Skill) => {
    setSkills(prev => [...prev, { ...skill, enabled: true, source: 'managed' as const }])
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      Productivity: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      Automation: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
      Analysis: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      Communication: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      Development: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      Media: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400',
      Security: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
      Utility: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    }
    return colors[category] || 'bg-gray-100 text-gray-800'
  }

  const getSourceIcon = (source: Skill['source']) => {
    switch (source) {
      case 'bundled': return '鉁?
      case 'managed': return '馃摝'
      case 'workspace': return '馃搧'
      case 'clawhub': return '馃З'
    }
  }

  const filteredSkills = activeTab === 'clawhub' ? clawhubSkills : skills.filter(s => s.source === activeTab)

  const tabs = [
    { id: 'bundled', label: '鍐呯疆鎶€鑳?, count: skills.filter(s => s.source === 'bundled').length },
    { id: 'managed', label: '鎵樼鎶€鑳?, count: skills.filter(s => s.source === 'managed').length },
    { id: 'workspace', label: '宸ヤ綔鍖?, count: skills.filter(s => s.source === 'workspace').length },
    { id: 'clawhub', label: 'ClawHub', count: clawhubSkills.length },
  ] as const

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-8 px-6" aria-label="Tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
              <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${
                activeTab === tab.id 
                  ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredSkills.map(skill => (
            <div
              key={skill.id}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{getSourceIcon(skill.source)}</span>
                  <h3 className="font-semibold">{skill.name}</h3>
                </div>
                <span className="text-xs text-gray-500">v{skill.version}</span>
              </div>
              
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">{skill.description}</p>
              
              <div className="flex flex-wrap gap-2 mb-3">
                <span className={`px-2 py-1 rounded-full text-xs ${getCategoryColor(skill.category)}`}>
                  {skill.category}
                </span>
                {skill.tags.map(tag => (
                  <span key={tag} className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded-full text-xs">
                    {tag}
                  </span>
                ))}
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  {skill.author && `浣滆€? ${skill.author}`}
                </span>
                
                {activeTab === 'clawhub' ? (
                  <button
                    onClick={() => installSkill(skill)}
                    className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
                  >
                    瀹夎
                  </button>
                ) : (
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={skill.enabled}
                      onChange={() => toggleSkill(skill.id)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                  </label>
                )}
              </div>
            </div>
          ))}
        </div>

        {filteredSkills.length === 0 && (
          <div className="flex items-center justify-center h-64 text-gray-500">
            {activeTab === 'workspace' ? '宸ヤ綔鍖烘妧鑳戒负绌? : 
             activeTab === 'managed' ? '鏆傛棤鎵樼鎶€鑳? : 
             '鏆傛棤鎶€鑳?}
          </div>
        )}
      </div>
    </div>
  )
}
