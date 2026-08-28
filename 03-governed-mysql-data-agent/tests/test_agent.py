import tempfile
import unittest
from pathlib import Path

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
            ["resolve_metric", "validate_sql", "execute_sql", "verify_evidence"],
        )
        self.assertEqual(
            result["verification"],
            {"method": "metric_key_present_and_non_null", "passed": True},
        )
        self.assertTrue(result["verified"])

    def test_unknown_metric_stops_before_policy_and_has_no_verification_signal(self):
        result = DataAgent("unused.db").answer("not a known metric")

        self.assertEqual(result["status"], "NEED_CLARIFICATION")
        self.assertEqual(result["trace"], ["resolve_metric"])
        self.assertNotIn("verified", result)


if __name__ == "__main__":
    unittest.main()
