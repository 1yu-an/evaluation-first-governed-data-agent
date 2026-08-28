import unittest

from src.policy import evaluate_sql_policy, validate_sql


class PolicyTest(unittest.TestCase):
    def test_select(self):
        self.assertTrue(validate_sql("SELECT * FROM orders")[0])

    def test_delete(self):
        self.assertFalse(validate_sql("DELETE FROM orders")[0])

    def test_multi(self):
        self.assertFalse(validate_sql("SELECT 1; DROP TABLE x")[0])

    def test_structured_policy_result_records_real_trace(self):
        result = evaluate_sql_policy("DELETE FROM orders")

        self.assertEqual(
            result,
            {
                "allowed": False,
                "reason": "only SELECT is allowed / 仅允许 SELECT",
                "trace": ["validate_sql"],
            },
        )


if __name__ == "__main__":
    unittest.main()
