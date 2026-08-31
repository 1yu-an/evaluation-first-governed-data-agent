from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.demo import initialize_expenses


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("expenses.db")
    database = initialize_expenses(target)
    print(f"Expenses database initialized at {database.resolve()}")
