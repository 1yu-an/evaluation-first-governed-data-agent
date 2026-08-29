# 03 Governed MySQL Data Agent / 受治理的 MySQL 数据 Agent

不是普通 Text-to-SQL。重点是 semantic layer（业务语义层）、query safety（查询安全）、EXPLAIN-like validation（执行前验证）和 evidence（结果证据）。

默认使用 SQLite 运行确定性 demo；`schema_mysql.sql` 给出 MySQL 版本结构。
SQL Policy 使用 `sqlglot` 的 MySQL parser/AST，因此先安装项目依赖：

```bash
python3 -m pip install -r requirements.txt
```

当前真实调用链：

`question -> build_semantic_plan -> validate_sql -> SQLite execute -> verify_evidence -> result`

`SemanticPlan` 最小契约显式包含 `metric`、`filters`、`status` 和 `reason`。
只有 `READY` plan 可以进入 SQL policy 与执行。多个 metric、合同定义的模糊
scope，以及已识别但当前不可执行的 region filter 会在 SQL 之前返回
`NEED_CLARIFICATION`，不会静默退化为无过滤查询。

SQL Policy 只允许一条解析成功且只读的 SELECT query，包括
`WITH ... SELECT`。它根据 AST 节点拒绝写操作、多语句、锁定查询、解析失败
及不支持的语句类型，不扫描字符串字面量中的禁用词。

只有实际执行的阶段才写入结果的 `trace`。成功查询的 `verified` 来自一个最小
确定性检查：结果必须包含目标 metric 的非空值。该信号不是生产级独立验证或
evidence provenance（证据来源）证明。

## Run / 运行
```bash
python3 scripts/init_demo.py
python3 -m src.cli "revenue"
python3 -m unittest discover -s tests -v
```

项目 00 从外部运行 03 集成基准；03 的核心代码不依赖 00：

```bash
cd ../00-agent-eval-harness
python3 -m src.integration_benchmark
```

## What to build next / 下一步
- 接真实 MySQL，并使用只读账号。
- 增加 schema retrieval + metric retrieval。
- 用 LLM 生成 logical plan，再由 deterministic compiler 转 SQL。
- 增加 100 个 NL→business metric eval cases。
