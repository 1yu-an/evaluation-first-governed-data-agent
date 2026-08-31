# 03 Governed MySQL Data Agent / 受治理的 MySQL 数据智能体

这是一个 **Evaluation-first Governed Data Agent prototype（评测优先的受治理数据
智能体原型）**。它解决的核心问题不是“怎样从自然语言生成更多 SQL”，而是：怎样只
接受系统能够确定解释、确定编译、限制权限并验证结果契约的业务问题；其余问题安全地
返回澄清。

稳定 v1 基线：`5afe98c157d416a797b473c5bbea21c87cbdfdb0`。v2 在保持下列
固定评测结果的前提下增加个人数据库 Profile，不修改 Eval Set。

```text
Fixed Benchmark: 53 / 56 success
SAFE_FAILURE = 3
FALSE_SUCCESS = 0
UNSAFE_ALLOW = 0
OVER_BLOCK = 0
```

## v2 Personal-Use Data Agent / 个人使用版

v1 已证明治理链和安全边界，v2 解决的是另一个根因：此前要接入个人数据库，必须修改
`catalog.py`、`semantic.py` 和 `compiler.py`。现在业务知识位于外部、严格校验的 JSON
Domain Profile；Core Engine 只保留通用解析、有限编译模板、Policy、执行和验证。

v2 当前提供：

- [`profiles/demo.json`](profiles/demo.json)：完整承载 v1 订单领域，且仍是默认 Profile；
- [`profiles/expenses.json`](profiles/expenses.json)：非 demo 个人支出示例，包含 3 个指标、
  category 过滤和 6 行种子数据；
- 离线 Profile 校验与真实 MySQL `INFORMATION_SCHEMA.COLUMNS` 预检；
- `ask` 简洁答案、`explain` 无执行计划，以及旧位置参数 CLI 兼容模式；
- JSON 中禁止 raw SQL，只允许 `count/sum/avg/max` 与受控的
  `difference_of_sums` 两种有限操作结构。

V2.2 产品化加固还提供：

- 正常的根 `--help`、可操作的 `reason_code`/hint 和脱敏数据库诊断；
- `DATA_AGENT_PROFILE` 与 `DATA_AGENT_DB_PATH` 个人默认值；
- `init-profile` 合法最小模板，默认拒绝覆盖已有文件；
- expenses Profile 的显式 category/region/status scope fail-closed 覆盖；
- initialize → validate → explain → ask 的单一 smoke flow。

需求和设计决策见
[`PERSONAL_USE_V2_PRD.md`](../PERSONAL_USE_V2_PRD.md) 与
[`PERSONAL_USE_V2_DESIGN.md`](../PERSONAL_USE_V2_DESIGN.md)。V2.2 的真实摩擦、
候选排序和选择边界见
[`V2_2_HARDENING_PRD.md`](../V2_2_HARDENING_PRD.md)，最终本地、MySQL、Benchmark、
安全与托管 CI 证据见
[`V2_2_HARDENING_REPORT.md`](../V2_2_HARDENING_REPORT.md)。

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
Validated JSON Domain Profile
  ↓
Profile-driven Resolver
  ↓
SemanticPlan
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
| Domain Profile | 外部声明指标语言、有限维度、表列引用与批准操作 | 不含 raw SQL、凭据、Python hook 或任意表达式 |
| Governed Resolver | 用所选 Profile 的 canonical forms、aliases 和组合规则选择 metric；歧义时澄清 | 不生成 SQL，不使用 LLM 猜测语义 |
| SemanticPlan | 显式保存 metric、filters、status、reason | 不包含表名、字段名或 SQL |
| Deterministic Compiler | 把 READY plan 和已校验操作编译为模板 SQL 与独立 params | 不读取原始问题，不接受 raw SQL 或 Profile 新增执行代码 |
| AST SQL Policy | 使用 sqlglot MySQL AST 只允许一条只读 SELECT/CTE 查询 | 不证明查询的业务指标语义正确 |
| QueryExecutor | 执行 CompiledQuery；SQLite/MySQL 共享同一上游合同 | 不做语义解析或策略改写 |
| DB least privilege | MySQL runtime 账号只有目标数据库 SELECT 权限 | 不替代应用层 AST Policy |
| Strict Verification | 验证 exactly-one、预期 key、numeric、finite、non-null | 不独立证明 Compiler SQL 的完整业务语义正确 |
| Eval / Benchmark | 用固定案例测 State、Policy、Verification 与回归变化 | 不声称固定 56 条案例证明普遍安全 |

### Safety invariants / 安全不变量

1. 只有 `READY` SemanticPlan 可以进入 Compiler。
2. Profile 声明语义和有限操作；只有 Compiler 持有 SQL 模板。
3. filter value 与 SQL 结构分离，并作为 bound params 传递。
4. 所有编译 SQL 都必须通过 AST Policy。
5. MySQL Agent runtime 不读取管理员凭据，只使用 SELECT-only 账号。
6. ResultContract 失败时 fail closed，不返回 verified business evidence。
7. Profile 必须声明希望识别的 scope vocabulary；声明但不允许的维度会在 Compiler
   前安全失败，不会静默丢弃。

## Five-minute personal expenses flow / 5 分钟个人支出流程

只需要 Python 3.12+。以下是个人运行时安装，不需要 Java、Maven、MySQL、管理员凭据，
也不需要根目录的完整 dev dependencies。

### Windows PowerShell

```powershell
Set-Location 03-governed-mysql-data-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python scripts\init_expenses.py expenses.db
$env:DATA_AGENT_PROFILE = "profiles\expenses.json"
$env:DATA_AGENT_DB_PATH = "expenses.db"

python -m src.cli validate-profile
python -m src.cli explain "average expense for transport"
python -m src.cli ask "total expenses for groceries"
```

如果机器没有 Windows Python Launcher，将 `py -3.12` 替换为 Python 3.12+ 的
`python`。

### macOS / Linux

```bash
cd 03-governed-mysql-data-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python scripts/init_expenses.py expenses.db
export DATA_AGENT_PROFILE=profiles/expenses.json
export DATA_AGENT_DB_PATH=expenses.db

python -m src.cli validate-profile
python -m src.cli explain "average expense for transport"
python -m src.cli ask "total expenses for groceries"
```

配置优先级固定为：显式 `--profile` / `--db-path` > 对应环境变量 > 默认
`profiles/demo.json` / `demo.db`。运行 `python -m src.cli --help` 可查看所有命令。

最后一条命令输出简洁合同，不显示 SQL：

```json
{
  "status": "success",
  "profile_id": "expenses",
  "metric": "total_expenses",
  "filters": {"category": "food"},
  "value": 47.5,
  "verified": true,
  "evidence": {"row_count": 1, "result_key": "total_expenses"}
}
```

`explain` 会显示参数化 SQL 和 params，但返回 `executed=false`，不打开数据库。旧命令
`python -m src.cli "revenue"` 仍选择默认 demo Profile 并保留 v1 完整输出。

### Start a new Profile / 创建新 Profile

不要从空 JSON 或 111 行 expenses 配置开始。先生成一个通过生产 validator 的最小模板：

```powershell
python -m src.cli init-profile profiles\my_profile.json
python -m src.cli validate-profile --profile profiles\my_profile.json
```

命令不会连接数据库、检查数据、猜 metric、生成 raw SQL 或覆盖已有文件。替换模板中的
`replace_table`、metric meaning 和 phrases；需要 filters 时参考
[`profiles/expenses.json`](profiles/expenses.json)。Profile 应声明所有需要识别的维度标签，
即使某个维度不被当前 metric 允许；这样显式但不支持的 scope 会安全失败，而不是变成
无过滤查询。

### Actionable failures / 可操作错误

新式 CLI 失败始终是 JSON。安全语义拒绝使用 `status=safe_failure`；配置/数据库错误使用
`status=error`。`reason_code` 供脚本稳定判断，`reason` 保留具体细节，`hint` 在可以明确
修复时给出下一步。例如认证失败使用 `database_authentication_failed`，schema 不匹配使用
`schema_mismatch`。输出不会包含密码、DSN、敏感环境变量或 traceback。

### Connect a personal MySQL schema / 接入个人 MySQL

1. 用 `init-profile` 创建最小模板，或复制 `profiles/expenses.json` 作为 filter 示例；
   不要放入 SQL 或凭据。
2. 运行 `validate-profile` 做离线结构/引用/标识符检查。
3. 通过 shell 环境变量配置独立的 SELECT-only 运行账号。
4. 设置 `DATA_AGENT_EXECUTOR=mysql`，先运行
   `validate-profile --check-mysql-schema`；缺表或列会在业务查询前以
   `SCHEMA_MISMATCH` 失败。
5. 使用 `ask --profile <path> "<question>"` 查询；管理员凭据只供初始化使用，Agent
   runtime 只读取 `MYSQL_AGENT_*`。

Profile 的完整字段、标识符规则、有限操作和错误合同以 v2 Design 为准。当前不是 schema
自动发现器：用户需要明确写出想治理的指标，系统也不会因数据库里存在某列就自动开放它。

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

当前普通测试结果：`223 passed, 1 skipped, 13 subtests passed`，包含原有 v1 回归
以及新增 Profile/schema/expenses/CLI 覆盖。skip 是显式 opt-in
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
`acceptance_gate.py --with-mysql` 执行 10-case 真实 MySQL 集成测试。管理员 setup
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

`setup_mysql.py` 幂等创建 demo 与 expenses schema/seed，重置 Agent 账号权限，并只授予目标数据库
的 `SELECT`。真实测试直接绕过 AST Policy 尝试 UPDATE、INSERT、DELETE，证明数据库层
会独立拒绝写入；它还验证 SQLite/MySQL 业务 evidence 一致。

## Limitations / 工程边界

- 每个 Domain Profile 的指标和 filters 都是显式有限集合；当前不做 schema 自动发现。
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
3. [`profiles/demo.json`](profiles/demo.json) 与 [`profiles/expenses.json`](profiles/expenses.json)：外部业务语义和批准操作。
4. [`src/profile.py`](src/profile.py) 与 [`src/compiler.py`](src/compiler.py)：严格校验以及 SemanticPlan 到有限模板 SQL/params 的边界。
5. [`../00-agent-eval-harness/cases/03_integration_cases.json`](../00-agent-eval-harness/cases/03_integration_cases.json)：固定 56-case 外部评测合同。

补充安全边界可查看 [`src/verification.py`](src/verification.py) 与
[`src/executor.py`](src/executor.py)。
