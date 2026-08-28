# 04 Java Migration Agent / Java 迁移 Agent

一个专注于 Java 代码库升级的 engineering agent（工程 Agent），而不是通用 coding agent。

基线实现：扫描 Maven `pom.xml`、发现旧 Java/JUnit 版本、生成迁移计划、执行受限文本修改，并要求编译/测试作为 verification gate（验证门）。

## Run / 运行
```bash
python3 -m src.cli fixtures/legacy-app --dry-run
python3 -m unittest discover -s tests -v
```

## Upgrade ideas / 升级方向
- 真正调用 Maven/Gradle build sandbox。
- 用 git worktree 隔离修改。
- 每个 patch 后 compile/test，失败自动 rollback。
- 加 Spring Boot 2→3 migration rules。
- 输出 PR description 与 risk summary。
