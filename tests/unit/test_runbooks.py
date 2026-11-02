"""Tests for runbook library."""

from aws_incident_copilot.runbooks.library import (
    Runbook,
    search_runbooks,
)


class TestRunbookLibrary:
    """Tests for the RunbookLibrary class."""

    def test_load_default_runbooks(self, runbook_library):
        """Test that default runbooks are loaded."""
        assert len(runbook_library.runbooks) > 0

    def test_search_crashloopbackoff(self, runbook_library):
        """Test searching for CrashLoopBackOff runbook."""
        results = runbook_library.search("crashloopbackoff pod restart")

        assert len(results) > 0
        top_result, score = results[0]
        assert "crash" in top_result.id.lower() or "crash" in top_result.title.lower()
        assert score > 0.1

    def test_search_oom(self, runbook_library):
        """Test searching for OOM runbook."""
        results = runbook_library.search("oom memory exit code 137 killed")

        assert len(results) > 0
        top_result, _ = results[0]
        assert "oom" in top_result.id.lower() or "memory" in top_result.title.lower()

    def test_search_database_connections(self, runbook_library):
        """Test searching for database connection runbook."""
        results = runbook_library.search("database too many connections pool exhausted")

        assert len(results) > 0
        top_result, _ = results[0]
        assert "connection" in top_result.title.lower() or "database" in top_result.title.lower()

    def test_search_alb_5xx(self, runbook_library):
        """Test searching for ALB 5xx runbook."""
        results = runbook_library.search("alb 5xx 502 503 error loadbalancer")

        assert len(results) > 0
        top_result, _ = results[0]
        assert "alb" in top_result.id.lower() or "5xx" in top_result.title.lower()

    def test_search_no_results(self, runbook_library):
        """Test search with no matching results."""
        results = runbook_library.search("xyznonexistent123")

        assert len(results) == 0

    def test_search_limit(self, runbook_library):
        """Test search result limiting."""
        results = runbook_library.search("kubernetes pod", limit=2)

        assert len(results) <= 2

    def test_get_by_id(self, runbook_library):
        """Test getting runbook by ID."""
        runbook = runbook_library.get_by_id("rb-eks-crashloop")

        assert runbook is not None
        assert runbook.id == "rb-eks-crashloop"
        assert len(runbook.steps) > 0

    def test_get_by_id_not_found(self, runbook_library):
        """Test getting non-existent runbook."""
        runbook = runbook_library.get_by_id("nonexistent")

        assert runbook is None

    def test_get_by_service(self, runbook_library):
        """Test getting runbooks by service."""
        runbooks = runbook_library.get_by_service("eks")

        assert len(runbooks) > 0
        for rb in runbooks:
            assert "eks" in [s.lower() for s in rb.related_services]

    def test_add_custom_runbook(self, runbook_library):
        """Test adding a custom runbook."""
        custom_runbook = Runbook(
            id="custom-test",
            title="Custom Test Runbook",
            description="A test runbook",
            symptoms=["test symptom"],
            keywords=["customtest", "unique"],
            steps=["Step 1", "Step 2"],
            related_services=["custom-service"],
        )

        runbook_library.add_runbook(custom_runbook)

        assert runbook_library.get_by_id("custom-test") is not None

        results = runbook_library.search("customtest unique")
        assert len(results) > 0
        assert results[0][0].id == "custom-test"


class TestSearchRunbooksFunction:
    """Tests for the search_runbooks helper function."""

    def test_search_runbooks_returns_dicts(self):
        """Test that search_runbooks returns dictionaries."""
        results = search_runbooks("crashloopbackoff")

        assert isinstance(results, list)
        if len(results) > 0:
            assert isinstance(results[0], dict)
            assert "id" in results[0]
            assert "title" in results[0]
            assert "relevance_score" in results[0]

    def test_search_runbooks_with_limit(self):
        """Test search_runbooks with limit."""
        results = search_runbooks("kubernetes", limit=2)

        assert len(results) <= 2
