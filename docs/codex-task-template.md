# Codex Task Template / Codex 任务模板

每次给 Agent 下任务，尽量使用下面结构，避免“帮我把整个项目写完”。

## Goal / 目标
明确一个可验证结果。

## Scope / 范围
列出允许修改的目录和禁止修改的接口。

## Contract / 契约
输入、输出、异常、状态转换必须明确。

## Acceptance tests / 验收测试
至少给 3 个正常用例 + 2 个失败用例。

## Non-goals / 非目标
明确本次不做什么，防止 Agent 扩张范围。

## Review questions / 你需要人工回答的问题
- 为什么这个接口这样设计？
- 是否破坏安全边界？
- 是否让 eval 变差？
- 是否引入隐藏状态？
