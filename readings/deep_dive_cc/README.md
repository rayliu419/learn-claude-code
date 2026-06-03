# Claude Code 源码研读笔记

> 对 claude-code 源码关键机制的分析笔记（HTML 格式，由工具生成），软链到本目录便于统一查阅。

## 分析文档

| 文档 | 核心主题 |
|------|----------|
| [context-compaction-study.html](context-compaction-study.html) | **上下文压缩** — 摘要/裁剪机制，保持激活窗口大小 |
| [memory-system-analysis.html](memory-system-analysis.html) | **记忆系统** — 跨会话持久化知识存储的设计 |
| [subagent-analysis.html](subagent-analysis.html) | **子代理** — 独立上下文委派子任务的分发模式 |

## 学习路径定位

这些文档对应 `learn-claude-code` 教学仓库中以下章节的源码实现参考：

- Context Compaction → s06 上下文管理
- Memory System → s09 记忆系统
- Subagent → s04 子代理 / s16 多智能体团队
