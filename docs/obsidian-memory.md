# 第四层记忆：Obsidian Vault

更新日期：2026-10-03。

## 四层定义

| 层 | 职责 | 当前实现 |
| --- | --- | --- |
| 1 工作记忆 | 当前会话上下文与压缩 | 保留原实现 |
| 2 核心记忆 | 用户资料、事实与偏好 | Markdown，REST 按登录用户隔离 |
| 3 情节记忆 | 对话和任务经验摘要 | Markdown，REST 按登录用户隔离 |
| 4 程序性记忆 | 可复用流程与操作步骤 | Obsidian 兼容 Vault 的 `procedures/` |

第四层保留程序性记忆的语义，通过 Obsidian 兼容格式组织服务流程、接单步骤和经营经验。订单、金额与履约状态由业务数据库负责，笔记中的步骤不替代用户交易授权。

## 已实现

- 使用 Markdown 与 YAML properties 保存流程，支持中文名称。
- 读取 `[[wikilinks]]`，查询反向链接并展示关联笔记。
- 按关键词检索流程，复用原程序性记忆检索入口。
- 提供 `/memories` 页面，可记录、搜索和查看流程、属性及反向链接。
- 支持 Obsidian URI，在部署设备上打开对应笔记。
- REST 接口要求登录；共同底座 DefaultOrchestrator 使用会话用户的记忆目录检索。
- 阻止 Vault 路径穿越和指向目录外的符号链接，限制文件大小与扫描数量。

这是本地 Vault 文件适配，不调用桌面 CLI，不执行笔记内容，不自动安装或调用 Obsidian 插件。检索目前是关键词检索，不是向量语义检索。手动在 Obsidian 中修改流程后，下次检索读取最新内容。

## 目录与配置

默认服务器目录：

```text
~/.openagentic/memory/users/<user_uuid>/
├── core/
├── episodes/
├── procedures/   # 第四层流程
└── MEMORY.md
```

可通过 `OPENAGENTIC_MEMORY_DIR` 修改记忆根目录。需要单独存放 Vault 时，部署者设置：

```bash
export OPENAGENTIC_OBSIDIAN_ROOT=/path/to/openagentic-vaults
```

第四层写入 `<OPENAGENTIC_OBSIDIAN_ROOT>/<user_uuid>/procedures/`。每个账号只访问自己的目录，HTTP 请求不能自行指定服务器根目录。可以在部署机器的 Obsidian 中将这个用户目录作为 Vault 打开；未配置时直接打开默认用户记忆目录。

远程部署时，服务器路径与用户设备路径不同，需要另行安排同步或本地挂载；打开 URI 不会自动把服务器笔记同步到手机或电脑。当前不提供自动同步。

## API

除现有 core/episodes/procedures 接口外，新增：

| 接口 | 用途 |
| --- | --- |
| `GET /api/memory/vault` | 当前用户 Vault 信息与已支持能力 |
| `GET /api/memory/vault/search?q=...` | 检索第四层流程 |
| `GET /api/memory/vault/note?path=procedures/...md` | 查看当前用户笔记、属性、链接和反向链接 |
| `POST /api/memory/procedures` | 保存流程到 Vault |

所有接口要求 Bearer access token。历史共享 REST 目录不会自动归给任意用户；需要迁移旧笔记时，由部署者明确归属后处理。切换外置 Vault 根目录也不会自动移动已有流程。

## 当前边界

CLI 保留单用户本地目录。旧 `extensions/channels/channel_runner.py` 仍有共享记忆逻辑；其迁移至按用户授权的共同底座需后续完成，不能把旧渠道视为已具备多商家记忆隔离。当前 Vault 以用户隔离，尚不提供商家团队共享、成员 ACL 或原生 Obsidian 插件集成。

官方格式与打开协议参考：[Obsidian Vault](https://docs.obsidian.md/Plugins/Vault)、[Obsidian URI](https://help.obsidian.md/Extending%2BObsidian/Obsidian%2BURI)。实现和本地验证无需访问这些网站。

## 与商业应用的关系

Vault 与四层记忆属于通用底座，不依赖商家、订单或商业页面。商业应用的 `commerce/engine.py` 仅通过公开记忆/检索接口注入当前账号的上下文；UI 在 `ui/src/apps/commerce/pages/MemoriesPage.tsx` 提供入口。关闭商业应用后，标准 `/api/memory/*` 仍可独立使用。分层规则见 [架构约束](commerce-architecture.md)。
