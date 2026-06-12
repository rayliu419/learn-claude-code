# CLAUDE.md

## This is Leaked Source Code

This repository contains leaked source code from Anthropic's Claude Code CLI. It is **not a working development project** — there is no `package.json`, build system, or test suite.

**Do not attempt to build, install, or run code from this repository.**

## Purpose

This is an archival/study repository. The `README.md` contains a breakdown of the architecture:
- `src/main.tsx` — CLI entrypoint (~803KB, uses Commander.js + React/Ink)
- `src/tools/` — 40+ agent tools
- `src/services/` — Backend (MCP, OAuth, Analytics, autoDream)
- `src/coordinator/` — Multi-agent orchestration (Swarm)
- `src/buddy/` — Tamagotchi companion system
- `src/bridge/` — IDE integration layer

## Working in This Repo

Since this is static source code with no development workflow:
- No build commands available
- No test commands available
- No lint/typecheck commands available
- Refer to `README.md` for architectural documentation

## HTML 生成偏好

生成学习笔记类 HTML 时遵循以下样式规范：

- **配色**：浅绿色主题，背景 `#f5faf6`，面板 `#e8f5ec`，边框 `#c3dbcc`，文字 `#2d3a31`
- **字体大小**：`body` 使用 `font-size:13px; line-height:1.45`，紧凑排版
  - h1: 1.35em, h2: 1.2em, h3: 1.02em, h4: 0.95em
  - code: 0.88em, pre: 0.8em, table: 0.9em
- **间距**：段落 `margin:6px 0`，列表项 `margin:2px 0`，减少留白
- 参考 `/Users/liurui/workspace/claude-code/memory-system-analysis.html` 的整体风格

## 笔记生成偏好

- Summary + Details + Conclusion
- Summary 先给出总体的设计或者架构
- Details 解释细节
- Conclusion 再回顾Details和Summary的关系
