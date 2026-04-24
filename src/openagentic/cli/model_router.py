"""DeepSeek Pro / Flash 智能自动切换模块。

根据用户任务复杂度，自动在 DeepSeek V4 Pro 和 V4 Flash 之间切换：
- 高级任务 → deepseek/deepseek-v4-pro
- 普通任务 → deepseek/deepseek-v4-flash

分类方式：关键词 + 模式匹配（纯本地，零延迟，不调 LLM）
"""

from __future__ import annotations

# 高级任务关键词（命中任一 → Pro）
ADVANCED_KEYWORDS: list[str] = [
    "写代码",
    "写个代码",
    "实现",
    "重构",
    "修复bug",
    "修复 bug",
    "修复",
    "架构",
    "优化性能",
    "性能优化",
    "算法",
    "安全",
    "框架",
    "设计模式",
    "review",
    "refactor",
    "debug",
    "debugging",
    "optimize",
    "optimization",
    "architecture",
    "implement",
    "implementation",
    "编写",
    "修改框架",
    "性能瓶颈",
    "漏洞",
    "加密",
    "并发",
    "分布式",
    "微服务",
    "单元测试",
    "集成测试",
    "代码审查",
    "code review",
    "性能调优",
    "内存泄漏",
    "死锁",
    "多线程",
    "异步",
    "SQL 优化",
    "索引优化",
    "系统设计",
    "system design",
    "接口设计",
    "API 设计",
    "数据库设计",
    "缓存策略",
    "负载均衡",
    "高可用",
    "容灾",
    "降级",
    "限流",
    "熔断",
    "幂等",
    "一致性",
    "CAP",
    "分布式锁",
    "分布式事务",
    "消息队列",
    "事件驱动",
    "领域驱动",
    "DDD",
    "CQRS",
    "事件溯源",
    "重构代码",
    "clean code",
    "SOLID",
    "KISS",
    "DRY",
    "YAGNI",
    "代码规范",
    "lint",
    "linting",
    "静态分析",
    "漏洞扫描",
    "渗透测试",
    "XSS",
    "CSRF",
    "SQL 注入",
    "认证",
    "授权",
    "OAuth",
    "OAuth2",
    "JWT",
    "SSO",
    "RBAC",
    "ABAC",
    "零信任",
    "安全审计",
    "威胁建模",
    "加密算法",
    "AES",
    "RSA",
    "TLS",
    "SSL",
    "HTTPS",
    "密钥管理",
    "密钥",
    "哈希",
    "哈希算法",
    "SHA",
    "bcrypt",
    "PBKDF2",
    "Argon2",
    # ── 文档与编辑 ──
    "更新",
    "修改",
    "编辑",
    "补充",
    "完善",
    "重写",
    "改写",
    "删除",
    "移除",
    "添加",
    "新增",
    "创建",
    "新建",
    "复制",
    "移动",
    "重命名",
    # ── 版本控制 ──
    "提交",
    "推送",
    "拉取",
    "合并",
    "分支",
    "git",
    "github",
    "commit",
    "push",
    "pull",
    "merge",
    "branch",
    "仓库",
    "版本控制",
    # ── 构建部署 ──
    "安装",
    "打包",
    "构建",
    "编译",
    "部署",
    "发布",
    "上线",
    "回滚",
    # ── 问题排查 ──
    "乱码",
    "编码",
    "报错",
    "错误",
    "异常",
    "崩溃",
    "卡顿",
    "慢",
    "排查",
    "定位",
    "修复",
    # ── 配置与调整 ──
    "配置",
    "设置",
    "调整",
    "迁移",
    "升级",
    "降级",
    # ── 开发相关 ──
    "文档",
    "readme",
    "README",
    "注释",
    "代码",
    "源码",
    "源文件",
    "脚本",
    "函数",
    "类",
    "模块",
    "接口",
    "组件",
    "页面",
    "路由",
    # ── 英语技术动词 ──
    "update",
    "modify",
    "change",
    "edit",
    "add",
    "remove",
    "delete",
    "create",
    "write",
    "fix",
    "improve",
    "upgrade",
    "migrate",
    "deploy",
    "release",
    "build",
    "compile",
    "install",
    "config",
    "configure",
    "setup",
    "test",
    "testing",
    "document",
    "documentation",
]

# 简单明确的高级任务判断前缀
ADVANCED_PREFIXES: list[str] = [
    "帮我写",
    "帮我改",
    "帮我实现",
    "帮我重构",
    "帮我优化",
    "帮我修复",
    "帮我设计",
    "帮我排查",
    "请写",
    "请实现",
    "请重构",
    "请优化",
    "请修复",
    "请设计",
    "请排查",
    "写一个",
    "写个",
    "实现一个",
    "实现个",
    "重构一下",
    "优化一下",
    "修复一下",
    "设计一个",
    "排查一下",
]

# 普通任务关键词（明确命中 → Flash，优先级高于高级关键词）
SIMPLE_KEYWORDS: list[str] = [
    "你好",
    "hello",
    "hi",
    "谢谢",
    "thank",
    "再见",
    "bye",
    "解释",
    "什么是",
    "介绍一下",
    "什么是",
    "告诉我",
    "怎么用",
    "如何使用",
    "什么是",
    "区别",
    "对比",
    "比较",
    "有哪些",
    "列表",
    "列举",
    "推荐",
    "建议",
    "帮我查",
    "查一下",
    "搜索",
    "翻译",
    "总结",
    "概括",
    "摘要",
]


def classify_task(user_input: str) -> str:
    """对用户输入进行任务复杂度分类。

    Returns:
        "pro"  — 高级任务，使用 DeepSeek V4 Pro
        "flash" — 普通任务，使用 DeepSeek V4 Flash
    """
    text = user_input.strip()
    if not text:
        return "flash"

    text_lower = text.lower()

    # 1) 先检查简单任务关键词（明确闲聊/查资料类）
    for kw in SIMPLE_KEYWORDS:
        if kw.lower() in text_lower:
            return "flash"

    # 2) 检查高级关键词
    for kw in ADVANCED_KEYWORDS:
        if kw.lower() in text_lower:
            return "pro"

    # 3) 检查高级前缀
    for prefix in ADVANCED_PREFIXES:
        if text.startswith(prefix):
            return "pro"

    # 4) 默认 → 普通任务
    return "flash"


def route_model(
    user_input: str,
    provider: str,
    current_model: str,
    *,
    automodel_enabled: bool = True,
) -> tuple[str, str | None]:
    """根据任务复杂度路由到合适的模型。

    Args:
        user_input: 用户原始输入
        provider: 当前厂商
        current_model: 当前模型名
        automodel_enabled: 是否启用自动切换

    Returns:
        (model_to_use, hint_message_or_None)
    """
    if not automodel_enabled:
        return current_model, None

    # 仅对 deepseek provider 生效
    if provider != "deepseek":
        return current_model, None

    classification = classify_task(user_input)
    target_model = "deepseek/deepseek-v4-pro" if classification == "pro" else "deepseek/deepseek-v4-flash"

    # 如果目标模型和当前模型相同，不提示
    if target_model == current_model:
        return current_model, None

    short_name = "deepseek-v4-pro" if classification == "pro" else "deepseek-v4-flash"
    hint = f"[auto → {short_name}]"
    return target_model, hint


def automodel_status(provider: str, automodel_enabled: bool) -> str:
    """返回 /automodel 状态描述。"""
    state = "ON" if automodel_enabled else "OFF"
    if provider != "deepseek":
        return f"/automodel: {state} (当前 provider 为 {provider}，自动切换仅对 deepseek 生效)"
    return f"/automodel: {state} — 高级任务 → deepseek-v4-pro，普通任务 → deepseek-v4-flash"
