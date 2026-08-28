# Suggested Agent/Codex Work Queue / 建议交给 Agent/Codex 的任务队列

按顺序执行，每次只发一个可验收任务。

1. 为 `00-agent-eval-harness` 增加 Markdown report exporter，并补 10 个 tests。
2. 为 `03-governed-mysql-data-agent` 把 SQLite adapter 抽成 `DatabaseAdapter` 接口，再增加 MySQL adapter。
3. 为 Data Agent 增加 SQL AST parser 和 LIMIT enforcement。
4. 为 `01-agent-control-plane` 增加 `ToolExecutor` interface 与 HTTP/MCP mock adapters。
5. 为 Control Plane 增加 JWT authentication、RBAC 和 approval table。
6. 为 Control Plane 增加 BM25/embedding hybrid tool router，并做 token/accuracy benchmark。
7. 为 `02-verified-browser-ops-agent` 增加 Playwright adapter 和本地 demo web app。
8. 为 Browser Agent 增加 verification registry 和 recovery/replan。
9. 为 `04-java-migration-agent` 增加 git worktree sandbox + Maven command runner。
10. 为 `06-a2a-spring-boot-starter` 对照最新官方规范写 conformance matrix。

每项都要求：tests + docs + benchmark/failure case，不接受“代码能跑”作为唯一验收条件。
