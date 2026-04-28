import { useEffect, useState } from 'react'
import { useApi, type SkillInfo } from '../lib/api'

export type { SkillInfo as Skill }

export function SkillsPage() {
  const api = useApi()
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadSkills()
  }, [])

  const loadSkills = async () => {
    setLoading(true)
    setError(null)
    const resp = await api.skills.list()
    if (!resp.success || !resp.data) {
      setError(resp.error || '加载技能失败')
      setLoading(false)
      return
    }
    setSkills(resp.data)
    setLoading(false)
  }

  const toggleSkill = (skillId: string) => {
    setSkills(prev => prev.map(skill =>
      skill.id === skillId ? { ...skill, enabled: !skill.enabled } : skill
    ))
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
      General: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
    }
    return colors[category] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <h2 className="text-lg font-semibold">已安装技能</h2>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-gray-500">加载中...</div>
        ) : error ? (
          <div className="flex items-center justify-center h-64 text-red-500">{error}</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {skills.map(skill => (
              <div
                key={skill.id}
                className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold">{skill.name}</h3>
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
                    {skill.allowed_tools && `${skill.allowed_tools.length} tools`}
                  </span>

                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={skill.enabled}
                      onChange={() => toggleSkill(skill.id)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && skills.length === 0 && (
          <div className="flex items-center justify-center h-64 text-gray-500">
            暂无技能
          </div>
        )}
      </div>
    </div>
  )
}
