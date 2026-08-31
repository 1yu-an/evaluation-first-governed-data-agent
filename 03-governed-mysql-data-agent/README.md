# 03 Governed MySQL Data Agent / 受治理的 MySQL 数据智能体

这是一个 **Evaluation-first Governed Data Agent prototype（评测优先的受治理数据
智能体原型）**。它解决的核心问题不是“怎样从自然语言生成更多 SQL”，而是：怎样只
接受系统能够确定解释、确定编译、限制权限并验证结果契约的业务问题；其余问题安全地
返回澄清。

当前冻结版本：`68795ef10b5c54a999eae3cc2e956595030cf1df`

```text
Fixed Benchmark: 53 / 56 success
SAFE_FAILURE = 3
FALSE_SUCCESS = 0
UNSAFE_ALLOW = 0
OVER_BLOCK = 0
```

## Why this is not ordinary Text-to-SQL / 为什么不是普通 Text-to-SQL

普通 Text-to-SQL 的主要目标通常是把开放式语言转换成 SQL。本项目先定义受治理的
business metrics、filters、compiler strategies 和 result contracts，再决定问题是否
可执行。用户不能选择任意表、字段、聚合、谓词或原始 SQL。无法唯一映射到批准语义的
表达会返回 `NEED_CLARIFICATION`，不会猜测一个看似合理的查询。

最大风险不是 SQL 语法失败，而是返回一个形式正确但业务范围错误的数字。固定 Eval Set
中的早期案例曾暴露“丢失 region scope 后仍 verified=true”的 false success；显式
SemanticPlan、确定性 Compiler 和严格 ResultContract 正是围绕该风险建立的。

## What this project is / 项目是什么

- deterministic governance（确定性治理）
- fail-closed semantics（无法证明语义时安全澄清）
- database least privilege（数据库最小权限）
- regression evidence（固定评测集上的可复现改进证据）

## What this project is not / 项目不是什么

- general-purpose Text-to-SQL platform（通用文本转 SQL 平台）
- arbitrary SQL agent（任意 SQL 智能体）
- production BI platform（生产级 BI 平台）
- data warehouse（数据仓库）
- LLM semantic parser（大语言模型语义解析器）
- production-ready database infrastructure（生产级数据库基础设施）

## Architecture / 架构

```text
Question
  ↓
Governed Resolver
  ↓
SemanticPlan
  ↓
Metric Catalog
  ↓
Deterministic Compiler
  ↓
AST SQL Policy
  ↓
QueryExecutor
  ↓
SQLite / MySQL
  ↓
Database Least Privilege
  ↓
Strict Result Verification
  ↓
Eval / Benchmark / Regression Gate
```

| Layer | Responsibility / 职责 | Does not own / 不负责 |
|---|---|---|
| Governed Resolver | 用批准的 canonical forms、aliases 和组合规则选择 metric；歧义时澄清 | 不生成 SQL，不使用 LLM 猜测语义 |
| SemanticPlan | 显式保存 metric、filters、status、reason | 不包含表名、字段名或 SQL |
| Metric Catalog | 声明业务含义、resolver metadata、ResultContract、白名单 strategy | 不包含 raw SQL 或任意 aggregation/predicate 配置 |
| Deterministic Compiler | 把 READY plan 编译成固定 SQL 与独立 params | 不读取原始问题，不接受用户选择 SQL 结构 |
| AST SQL Policy | 使用 sqlglot MySQL AST 只允许一条只读 SELECT/CTE 查询 | 不证明查询的业务指标语义正确 |
| QueryExecutor | 执行 CompiledQuery；SQLite/MySQL 共享同一上游合同 | 不做语义解析或策略改写 |
| DB least privilege | MySQL runtime 账号只有目标数据库 SELECT 权限 | 不替代应用层 AST Policy |
| Strict Verification | 验证 exactly-one、预期 key、numeric、finite、non-null | 不独立证明 Compiler SQL 的完整业务语义正确 |
| Eval / Benchmark | 用固定案例测 State、Policy、Verification 与回归变化 | 不声称固定 56 条案例证明普遍安全 |

### Safety invariants / 安全不变量

1. 只有 `READY` SemanticPlan 可以进入 Compiler。
2. Catalog 声明语义；只有 Compiler 持有固定 SQL。
3. filter value 与 SQL 结构分离，并作为 bound params 传递。
4. 所有编译 SQL 都必须通过 AST Policy。
5. MySQL Agent runtime 不读取管理员凭据，只使用 SELECT-only 账号。
6. ResultContract 失败时 fail closed，不返回 verified business evidence。

## Five-minute SQLite demo / 5 分钟 SQLite 演示

要求 Python 3.12+。从仓库根目录执行。

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Set-Location 03-governed-mysql-data-agent
python scripts\init_demo.py
python -m src.cli "highest completed order total"
```

如果机器没有 Windows Python Launcher，请将第一条命令中的 `py -3.12` 替换为
本机 Python 3.12+ 可执行文件，例如 `python`。

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cd 03-governed-mysql-data-agent
python scripts/init_demo.py
python -m src.cli "highest completed order total"
```

预期核心结果：

```text
status = OK
metric = max_completed_order_total
evidence = {"max_completed_order_total": 120.0}
verified = true
```

完整 trace 为 Resolver → Compiler → AST Policy → Executor → Verification。

## Dependency model / 依赖模型

- `03-governed-mysql-data-agent/requirements.txt` 只锁定 03 runtime dependencies：
  `sqlglot==30.13.0` 和 `mysql-connector-python==9.7.0`。
- 根目录 `requirements-dev.txt` 复用上述 runtime pins，并锁定
  `pytest==9.1.1`，用于 03 tests、00 tests 和 fresh-environment 验证。
- 00 的评测框架源码本身只使用 Python 标准库；其 tests 需要 pytest。03 系统
  Benchmark 会动态加载 03 runtime，因此也需要 03 的 runtime dependencies。

## Tests and fixed Benchmark / 测试与固定基准

以下每个命令块都从仓库根目录开始，并假设已经创建、激活 `.venv`，且执行过：

```text
python -m pip install -r requirements-dev.txt
```

### Project 03 tests

```bash
cd 03-governed-mysql-data-agent
python -m pytest -q
```

当前普通测试结果：`172 passed, 1 skipped, 13 subtests passed`。skip 是显式 opt-in
的真实 MySQL 模块。

### Project 00 tests

```bash
cd 00-agent-eval-harness
python -m pytest -q
```

当前结果：`59 passed`。

### Fixed 56-case system Benchmark

```bash
cd 00-agent-eval-harness
python -m src.integration_benchmark
```

该命令创建隔离 SQLite demo，动态调用真实 03 runtime，并生成忽略于 Git 的
`reports/03-integration.json` 与 `reports/03-integration.md`。固定 Eval Set 不保存
`actual`，也没有为提高分数而修改。

最终结果为 `53 / 56`。这不是未完成状态。以下三个表达存在真实业务歧义，因此刻意
保留为 `NEED_CLARIFICATION`，且只执行 Resolver：

- `money made`
- `turnover`
- `fulfilled purchases`

它们共同构成 3 个 SAFE_FAILURE；最终仍为 `FALSE_SUCCESS=0`、
`UNSAFE_ALLOW=0`、`OVER_BLOCK=0`。

## Automated CI Regression Gate / 自动化持续集成回归门

GitHub Actions 的单一 Python 3.12 job 从干净 checkout 安装根目录
`requirements-dev.txt`，然后运行 repository validation、完整 03 tests、完整
00 tests，以及带 `config/03_regression_gate.json` 的固定 56-case Benchmark。
Benchmark report 会直接输出互斥的 safety classification；gate 除了检查既有机器
可读阈值，还会无条件硬门禁 `FALSE_SUCCESS=0` 与 `UNSAFE_ALLOW=0`，因此即使聚合
分数仍达标，这两项安全退化也会返回非零退出码。00 的集成测试同时锁定 56-case
Eval Set SHA-256，并断言最终 `53/56`、`SAFE_FAILURE=3`、
`FALSE_SUCCESS=0`、`UNSAFE_ALLOW=0` 和 `OVER_BLOCK=0`。

CI 的 Benchmark 仍使用确定性 SQLite，同时 job 会创建一次性 MySQL 8.0 service
container，使用仅限该次运行的测试凭据调用现有 `setup_mysql.py`，再通过
`acceptance_gate.py --with-mysql` 执行 8-case 真实 MySQL 集成测试。管理员 setup
身份与 Agent runtime 身份分离，Agent 仅获得 demo database 的 `SELECT`。本地真实
MySQL 仍按下节说明显式 opt-in，因为本地环境需要自行准备数据库与凭据。

## Engineering Evolution / 工程演进

每个数字均来自对应 commit 上固定 56-case 系统集成测试的断言；Eval Set 保持不变。

| Stage / 阶段 | Root Cause / Change / 根因与改进 | Benchmark |
|---|---|---:|
| Baseline v0 | initial governed agent / 初始受治理智能体 | 37/56 |
| Semantic safety | prevent dropped scope/filter / 防止范围或过滤静默丢失 | 40/56 |
| AST Policy | remove regex over-blocking / 消除正则策略误阻止 | 42/56 |
| Filter compiler | deterministic region filters / 确定性地域过滤 | 43/56 |
| Governed Resolver | controlled paraphrase resolution / 受控改写解析 | 49/56 |
| Metric Catalog | payment/refund metrics / 付款与退款指标 | 51/56 |
| Pending Orders | governed status metric / 受治理状态指标 | 52/56 |
| MAX metric | governed MAX aggregation / 受治理最大值聚合 | 53/56 |

Real MySQL read-only execution 与 Strict Result Verification 主要增强 safety
architecture，而不是通过改变 Eval Set 刷高 Benchmark。完整 baseline Bad Cases 和风险
分析见 [`BASELINE_V0.md`](BASELINE_V0.md)。当前冻结快照见根目录
[`CURRENT_STATE.md`](../CURRENT_STATE.md)。

## Optional real MySQL reproduction / 可选真实 MySQL 复现

需要 MySQL 8.0（现有实例或 Docker）以及可创建 schema/user 的管理员凭据。Python
runtime **不会自动读取 `.env`**；[`.env.example`](.env.example) 只是变量名模板，
不要提交真实密码。

以下命令从 `03-governed-mysql-data-agent` 目录运行，并假设 dev dependencies 已安装。

如果使用 Docker，请先在当前 shell 设置下面的变量，再运行 `docker compose up -d`。
Compose 和后续 Python 进程会读取同一组 shell 环境变量。

### PowerShell

```powershell
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_DATABASE = "data_agent"
$env:MYSQL_ADMIN_USER = "root"
$env:MYSQL_ADMIN_PASSWORD = "replace-with-admin-password"
$env:MYSQL_AGENT_USER = "data_agent_ro"
$env:MYSQL_AGENT_PASSWORD = "replace-with-read-only-password"
$env:MYSQL_AGENT_HOST_PATTERN = "%"

# Optional when Docker is available:
docker compose up -d

python scripts\setup_mysql.py
$env:DATA_AGENT_EXECUTOR = "mysql"
python -m src.cli "highest completed order total"
$env:RUN_MYSQL_INTEGRATION = "1"
python -m pytest -q tests\test_mysql_integration.py
```

### POSIX shell

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DATABASE=data_agent
export MYSQL_ADMIN_USER=root
export MYSQL_ADMIN_PASSWORD=replace-with-admin-password
export MYSQL_AGENT_USER=data_agent_ro
export MYSQL_AGENT_PASSWORD=replace-with-read-only-password
export MYSQL_AGENT_HOST_PATTERN=%

# Optional when Docker is available:
docker compose up -d

python scripts/setup_mysql.py
export DATA_AGENT_EXECUTOR=mysql
python -m src.cli "highest completed order total"
export RUN_MYSQL_INTEGRATION=1
python -m pytest -q tests/test_mysql_integration.py
```

`setup_mysql.py` 幂等创建 demo schema/seed，重置 Agent 账号权限，并只授予目标数据库
的 `SELECT`。真实测试直接绕过 AST Policy 尝试 UPDATE、INSERT、DELETE，证明数据库层
会独立拒绝写入；它还验证 SQLite/MySQL 业务 evidence 一致。

## Limitations / 工程边界

- Metric Catalog 规模有限，只支持明确批准的业务指标和 filters。
- 三个真实歧义表达保持 `NEED_CLARIFICATION`，不会为了 56/56 强行映射。
- MySQL integration tests 是 opt-in，需要外部 MySQL 8.0 与管理员 setup 权限。
- 没有 production secret manager；凭据仅通过环境变量传入。
- 没有 ORM、connection pool 或 migration framework。
- 当前 verification 证明 ResultContract 的 key/type/cardinality/nullability，不独立证明
  Compiler SQL 的完整业务语义正确。

这些是原型的明确边界，不是未声明的生产能力。

## Recommended Review Path / 推荐审查路径

1. 本 README：问题、范围、运行路径与证据。
2. [`src/agent.py`](src/agent.py)：完整治理链编排与 fail-closed 行为。
3. [`src/catalog.py`](src/catalog.py)：业务语义、resolver metadata、contracts 和白名单 strategies。
4. [`src/compiler.py`](src/compiler.py)：SemanticPlan 到固定 SQL/params 的边界。
5. [`../00-agent-eval-harness/cases/03_integration_cases.json`](../00-agent-eval-harness/cases/03_integration_cases.json)：固定 56-case 外部评测合同。

补充安全边界可查看 [`src/verification.py`](src/verification.py) 与
[`src/executor.py`](src/executor.py)。
