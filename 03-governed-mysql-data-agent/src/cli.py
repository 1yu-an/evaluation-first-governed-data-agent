import json
import sys

from .agent import DataAgent
from .executor import ExecutionError, executor_from_env


def main() -> int:
    question = " ".join(sys.argv[1:]) or "revenue"
    try:
        executor = executor_from_env()
        result = DataAgent(executor=executor).answer(question)
    except ExecutionError as error:
        result = {
            "status": "ERROR",
            "reason": str(error),
            "trace": [],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "ERROR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
