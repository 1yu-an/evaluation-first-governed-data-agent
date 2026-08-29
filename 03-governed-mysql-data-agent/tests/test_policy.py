import unittest

from src.policy import (
    MULTIPLE_STATEMENTS,
    PARSE_FAILURE,
    UNSUPPORTED_STATEMENT,
    WRITE_STATEMENT,
    evaluate_sql_policy,
    validate_sql,
)


class PolicyTest(unittest.TestCase):
    def assert_allowed(self, sql):
        self.assertEqual(validate_sql(sql), (True, "ok"))

    def assert_blocked(self, sql, reason):
        self.assertEqual(validate_sql(sql), (False, reason))

    def test_basic_select_is_allowed(self):
        self.assert_allowed("SELECT * FROM orders")

    def test_read_only_cte_is_allowed(self):
        self.assert_allowed(
            "WITH completed AS (SELECT * FROM orders) "
            "SELECT * FROM completed"
        )

    def test_write_keyword_in_string_literal_is_allowed(self):
        self.assert_allowed("SELECT 'delete' AS documented_word")

    def test_select_is_case_insensitive(self):
        self.assert_allowed("sElEcT COUNT(*) FROM orders")

    def test_nested_read_only_select_is_allowed(self):
        self.assert_allowed(
            "SELECT id FROM orders WHERE total > "
            "(SELECT AVG(total) FROM orders)"
        )

    def test_trailing_semicolon_is_allowed(self):
        self.assert_allowed("SELECT id FROM orders;")

    def test_union_of_selects_is_one_read_only_query(self):
        self.assert_allowed("SELECT 1 AS value UNION SELECT 2 AS value")

    def test_unseen_write_words_in_literals_and_identifiers_are_allowed(self):
        self.assert_allowed(
            "SELECT 'DROP TABLE audit_log' AS note, `delete` "
            "FROM audit_log"
        )

    def test_unseen_write_words_in_comments_are_allowed(self):
        self.assert_allowed("SELECT 1 /* DELETE FROM orders */")

    def test_direct_write_statements_are_blocked_by_ast_type(self):
        statements = [
            "DELETE FROM orders",
            "UPDATE orders SET total = 0",
            "INSERT INTO orders (id) VALUES (9)",
            "DROP TABLE orders",
            "ALTER TABLE orders ADD COLUMN secret TEXT",
            "CREATE TABLE secrets (id INT)",
            "TRUNCATE TABLE orders",
        ]

        for sql in statements:
            with self.subTest(sql=sql):
                self.assert_blocked(sql, WRITE_STATEMENT)

    def test_write_node_nested_in_cte_is_blocked(self):
        self.assert_blocked(
            "WITH changed AS (DELETE FROM orders RETURNING id) "
            "SELECT * FROM changed",
            WRITE_STATEMENT,
        )

    def test_multiple_read_only_statements_are_blocked(self):
        self.assert_blocked("SELECT 1; SELECT 2", MULTIPLE_STATEMENTS)

    def test_select_followed_by_write_is_blocked_as_multiple_statements(self):
        self.assert_blocked(
            "SELECT 1; DROP TABLE orders",
            MULTIPLE_STATEMENTS,
        )

    def test_malformed_sql_fails_closed(self):
        self.assert_blocked("SELECT * FROM (", PARSE_FAILURE)

    def test_empty_and_comment_only_sql_fail_closed(self):
        for sql in ("", "   ", "-- no statement"):
            with self.subTest(sql=sql):
                self.assert_blocked(sql, PARSE_FAILURE)

    def test_parser_command_fallback_is_not_treated_as_a_query(self):
        self.assert_blocked(
            "REPLACE INTO orders VALUES (1, 'completed', 0, 'x')",
            UNSUPPORTED_STATEMENT,
        )

    def test_other_non_select_statement_types_are_blocked(self):
        for sql in (
            "GRANT SELECT ON analytics.* TO 'reader'@'localhost'",
            "REVOKE SELECT ON analytics.* FROM 'reader'@'localhost'",
            "SHOW TABLES",
        ):
            with self.subTest(sql=sql):
                self.assert_blocked(sql, UNSUPPORTED_STATEMENT)

    def test_locking_select_is_not_treated_as_read_only(self):
        self.assert_blocked(
            "SELECT * FROM orders FOR UPDATE",
            UNSUPPORTED_STATEMENT,
        )

    def test_structured_policy_result_records_real_trace(self):
        result = evaluate_sql_policy("DELETE FROM orders")

        self.assertEqual(
            result,
            {
                "allowed": False,
                "reason": WRITE_STATEMENT,
                "trace": ["validate_sql"],
            },
        )


if __name__ == "__main__":
    unittest.main()
