"""
Integration tests for SQL Query Editor API.

Tests the query endpoints including schema, examples, validation, and execution.
Run with: ./venv/bin/python tests/test_query_editor.py
Or pytest: ./venv/bin/python -m pytest tests/test_query_editor.py -v -s
"""
import os
import sys
import uuid

import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000"


class TestQueryEditorAPI:
    """Integration tests for query editor API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.client = httpx.Client(base_url=BASE_URL, timeout=30.0)
        self.test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"
        yield
        self.client.close()

    def _get_auth_token(self):
        """Get a dev auth token for testing."""
        self.client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": self.test_clerk_id, "email": "query_test@example.com"}
        )
        response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        return response.json()["token"]

    def test_01_schema_endpoint(self):
        """Test that schema endpoint returns table information."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/query/schema",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        assert isinstance(data["tables"], list)
        print(f"    Schema returned {len(data['tables'])} tables")
        print(f"    ✓ Schema endpoint works")

    def test_02_examples_endpoint(self):
        """Test that examples endpoint returns sample queries."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/query/examples",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "queries" in data
        assert "categories" in data
        assert len(data["queries"]) > 0
        assert len(data["categories"]) > 0

        # Check structure of example queries
        for q in data["queries"]:
            assert "name" in q
            assert "description" in q
            assert "category" in q
            assert "sql" in q

        print(f"    Examples returned {len(data['queries'])} queries")
        print(f"    Categories: {', '.join(data['categories'])}")
        print(f"    ✓ Examples endpoint works")

    def test_03_validate_endpoint_valid_query(self):
        """Test validation endpoint with valid query."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/query/validate",
            params={"sql": "SELECT * FROM messages LIMIT 10"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        assert data["error"] is None
        print(f"    ✓ Valid query passes validation")

    def test_04_validate_endpoint_invalid_query(self):
        """Test validation endpoint rejects dangerous queries."""
        token = self._get_auth_token()

        # Test blocked keywords
        dangerous_queries = [
            "DROP TABLE messages",
            "DELETE FROM messages",
            "INSERT INTO messages VALUES (1)",
            "UPDATE messages SET content = 'hacked'",
            "SELECT * FROM messages; DROP TABLE users",
        ]

        for sql in dangerous_queries:
            response = self.client.get(
                "/api/query/validate",
                params={"sql": sql},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == False
            assert data["error"] is not None
            print(f"    Blocked: {sql[:40]}...")

        print(f"    ✓ Dangerous queries are blocked")

    def test_05_execute_simple_query(self):
        """Test executing a simple SELECT query."""
        token = self._get_auth_token()

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELECT 1 as test_value", "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert "execution_time_ms" in data
        print(f"    Query returned {data['row_count']} rows in {data['execution_time_ms']:.2f}ms")
        print(f"    ✓ Query execution works")

    def test_06_execute_schema_query(self):
        """Test executing a query against actual schema tables."""
        token = self._get_auth_token()

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELECT COUNT(*) as total FROM messages", "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] >= 0
        print(f"    Message count query returned: {data['rows']}")
        print(f"    ✓ Schema table query works")

    def test_07_execute_complex_query(self):
        """Test executing a complex query with JOINs."""
        token = self._get_auth_token()

        complex_sql = """
        SELECT u.username, COUNT(m.id) as msg_count
        FROM users u
        LEFT JOIN messages m ON u.id = m.author_id
        GROUP BY u.id, u.username
        ORDER BY msg_count DESC
        LIMIT 5
        """

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": complex_sql, "limit": 100}
        )

        assert response.status_code == 200
        data = response.json()
        print(f"    Complex query returned {data['row_count']} rows")
        print(f"    ✓ Complex query execution works")

    def test_08_execute_blocked_query(self):
        """Test that blocked queries are rejected at execution."""
        token = self._get_auth_token()

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "DROP TABLE messages", "limit": 10}
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"    Blocked query error: {data['detail']}")
        print(f"    ✓ Blocked query rejected")

    def test_09_execute_syntax_error(self):
        """Test that syntax errors are handled gracefully."""
        token = self._get_auth_token()

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELEKT * FORM messages", "limit": 10}
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Error should not leak tenant information
        assert "tenant" not in data["detail"].lower()
        print(f"    Syntax error handled: {data['detail']}")
        print(f"    ✓ Syntax error handled gracefully")

    def test_10_execute_nonexistent_table(self):
        """Test querying non-existent table."""
        token = self._get_auth_token()

        response = self.client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELECT * FROM nonexistent_table_xyz", "limit": 10}
        )

        assert response.status_code == 400
        data = response.json()
        # Error should not leak tenant information
        assert "tenant" not in data["detail"].lower()
        print(f"    Non-existent table error: {data['detail']}")
        print(f"    ✓ Non-existent table handled")

    def test_11_requires_authentication(self):
        """Test that all endpoints require authentication."""
        endpoints = [
            ("GET", "/api/query/schema"),
            ("GET", "/api/query/examples"),
            ("GET", "/api/query/validate?sql=SELECT%201"),
            ("POST", "/api/query/execute"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = self.client.get(endpoint)
            else:
                response = self.client.post(endpoint, json={"sql": "SELECT 1"})

            assert response.status_code in [401, 403, 422], f"Expected auth error for {endpoint}, got {response.status_code}"

        print(f"    ✓ All endpoints require authentication")

    def test_12_example_queries_are_valid(self):
        """Test that all example queries pass validation."""
        token = self._get_auth_token()

        # Get examples
        examples_response = self.client.get(
            "/api/query/examples",
            headers={"Authorization": f"Bearer {token}"}
        )
        examples = examples_response.json()["queries"]

        # Validate each example
        valid_count = 0
        for example in examples:
            response = self.client.get(
                "/api/query/validate",
                params={"sql": example["sql"]},
                headers={"Authorization": f"Bearer {token}"}
            )
            data = response.json()
            if data["valid"]:
                valid_count += 1
            else:
                print(f"    Invalid example: {example['name']} - {data['error']}")

        print(f"    {valid_count}/{len(examples)} example queries are valid")
        assert valid_count == len(examples), "Some example queries are invalid"
        print(f"    ✓ All example queries pass validation")


def run_tests_standalone():
    """Run tests without pytest for quick debugging."""
    print("=" * 70)
    print("Running Query Editor Integration Tests")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"

    def get_token():
        client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": test_clerk_id, "email": "query_test@example.com"}
        )
        response = client.post(
            "/api/auth/dev/token",
            json={"clerk_id": test_clerk_id}
        )
        if response.status_code != 200:
            return None
        return response.json()["token"]

    try:
        # Test 1: Health check
        print("\n[1/12] Testing health check...")
        response = client.get("/health")
        assert response.status_code == 200
        print("    ✓ Health check passed")

        # Get auth token
        print("\n[2/12] Getting auth token...")
        token = get_token()
        if not token:
            print("    ✗ Failed to get token")
            return False
        print("    ✓ Got auth token")

        # Test 3: Schema endpoint
        print("\n[3/12] Testing schema endpoint...")
        response = client.get(
            "/api/query/schema",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        schema_data = response.json()
        print(f"    Found {len(schema_data['tables'])} tables")
        for table in schema_data['tables'][:5]:
            print(f"      - {table['name']}: {table['row_count']} rows, {len(table['columns'])} columns")
        print("    ✓ Schema endpoint works")

        # Test 4: Examples endpoint
        print("\n[4/12] Testing examples endpoint...")
        response = client.get(
            "/api/query/examples",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        examples_data = response.json()
        print(f"    Found {len(examples_data['queries'])} example queries")
        print(f"    Categories: {', '.join(examples_data['categories'])}")
        print("    ✓ Examples endpoint works")

        # Test 5: Validation - valid query
        print("\n[5/12] Testing validation (valid query)...")
        response = client.get(
            "/api/query/validate",
            params={"sql": "SELECT * FROM messages LIMIT 10"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        print("    ✓ Valid query passes validation")

        # Test 6: Validation - blocked queries
        print("\n[6/12] Testing validation (blocked queries)...")
        blocked_queries = ["DROP TABLE users", "DELETE FROM messages", "INSERT INTO users VALUES (1)"]
        for sql in blocked_queries:
            response = client.get(
                "/api/query/validate",
                params={"sql": sql},
                headers={"Authorization": f"Bearer {token}"}
            )
            data = response.json()
            assert data["valid"] == False
            print(f"      Blocked: {sql}")
        print("    ✓ Dangerous queries blocked")

        # Test 7: Execute simple query
        print("\n[7/12] Testing query execution (simple)...")
        response = client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELECT 1 as test, 'hello' as greeting", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"    Columns: {[c['name'] for c in data['columns']]}")
        print(f"    Rows: {data['rows']}")
        print(f"    Time: {data['execution_time_ms']:.2f}ms")
        print("    ✓ Simple query works")

        # Test 8: Execute complex query
        print("\n[8/12] Testing query execution (complex)...")
        complex_sql = """
        SELECT u.username, COUNT(m.id) as msg_count
        FROM users u
        LEFT JOIN messages m ON u.id = m.author_id
        GROUP BY u.id, u.username
        ORDER BY msg_count DESC
        LIMIT 5
        """
        response = client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": complex_sql, "limit": 100}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"    Returned {data['row_count']} rows")
        for row in data['rows'][:3]:
            print(f"      - {row}")
        print("    ✓ Complex query works")

        # Test 9: Execute example queries
        print("\n[9/12] Testing example query execution...")
        sample_examples = examples_data['queries'][:3]
        for example in sample_examples:
            response = client.post(
                "/api/query/execute",
                headers={"Authorization": f"Bearer {token}"},
                json={"sql": example['sql'], "limit": 10}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"      {example['name']}: {data['row_count']} rows")
            else:
                print(f"      {example['name']}: FAILED - {response.json().get('detail', 'Unknown error')}")
        print("    ✓ Example queries execute")

        # Test 10: Error handling - syntax error
        print("\n[10/12] Testing error handling (syntax)...")
        response = client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "SELEKT * FORM messages", "limit": 10}
        )
        assert response.status_code == 400
        data = response.json()
        assert "tenant" not in data["detail"].lower()
        print(f"    Error: {data['detail']}")
        print("    ✓ Syntax error handled (no tenant leak)")

        # Test 11: Error handling - forbidden operation
        print("\n[11/12] Testing error handling (forbidden)...")
        response = client.post(
            "/api/query/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"sql": "DROP TABLE messages", "limit": 10}
        )
        assert response.status_code == 400
        data = response.json()
        print(f"    Error: {data['detail']}")
        print("    ✓ Forbidden operation blocked")

        # Test 12: Validate all examples
        print("\n[12/12] Validating all example queries...")
        valid_count = 0
        for example in examples_data['queries']:
            response = client.get(
                "/api/query/validate",
                params={"sql": example['sql']},
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.json()["valid"]:
                valid_count += 1
        print(f"    {valid_count}/{len(examples_data['queries'])} examples are valid")
        assert valid_count == len(examples_data['queries'])
        print("    ✓ All example queries valid")

        print("\n" + "=" * 70)
        print("ALL QUERY EDITOR TESTS PASSED ✓")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = run_tests_standalone()
    sys.exit(0 if success else 1)
