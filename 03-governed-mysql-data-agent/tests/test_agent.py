import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agent import DataAgent
from src.demo import initialize_demo


class AgentTest(unittest.TestCase):
    def test_success_records_real_stages_and_deterministic_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = initialize_demo(Path(directory) / "demo.db")

            result = DataAgent(db_path).answer("revenue")

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["evidence"], {"revenue": 180.0})
        self.assertEqual(
            result["trace"],
            [
                "resolve_metric",
                "compile_query",
                "validate_sql",
                "execute_sql",
                "verify_evidence",
            ],
        )
        self.assertEqual(
            result["verification"],
            {
                "method": "strict_result_contract",
                "passed": True,
                "reason": "ok",
            },
        )
        self.assertTrue(result["verified"])

    def test_unknown_metric_stops_before_policy_and_has_no_verification_signal(self):
        result = DataAgent("unused.db").answer("not a known metric")

        self.assertEqual(result["status"], "NEED_CLARIFICATION")
        self.assertEqual(result["trace"], ["resolve_metric"])
        self.assertNotIn("verified", result)

    def test_compiled_query_is_policy_checked_before_database_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "must-not-be-opened.db"
            with patch(
                "src.agent.validate_sql", return_value=(False, "test block")
            ) as validate:
                result = DataAgent(db_path).answer(
                    "revenue for the south region"
                )

            validate.assert_called_once_with(result["sql"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(
                result["trace"],
                ["resolve_metric", "compile_query", "validate_sql"],
            )
            self.assertFalse(db_path.exists())


if __name__ == "__main__":
    unittest.main()
