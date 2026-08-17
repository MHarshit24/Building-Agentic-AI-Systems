"""
Unit tests for agent/tools/job_search.py — SerpAPI job search tool.
"""
import pytest
from unittest.mock import MagicMock, patch


# ── _format_job_listings ──────────────────────────────────────────────────────

class TestFormatJobListings:
    def test_empty_list_returns_no_results_message(self):
        from agent.tools.job_search import _format_job_listings
        result = _format_job_listings([])
        assert "No job listings found" in result

    def test_single_job_contains_title_and_company(self):
        from agent.tools.job_search import _format_job_listings
        jobs = [
            {
                "title": "Senior Python Developer",
                "company_name": "TechCorp",
                "location": "Remote",
                "via": "LinkedIn",
                "description": "Build amazing things with Python.",
                "job_highlights": [],
                "related_links": [],
            }
        ]
        result = _format_job_listings(jobs)
        assert "Senior Python Developer" in result
        assert "TechCorp" in result
        assert "Remote" in result
        assert "LinkedIn" in result

    def test_description_is_truncated_at_220_chars(self):
        from agent.tools.job_search import _format_job_listings
        long_desc = "x" * 300
        jobs = [
            {
                "title": "Dev", "company_name": "Co", "location": "NY",
                "description": long_desc, "job_highlights": [], "related_links": [],
            }
        ]
        result = _format_job_listings(jobs)
        assert "…" in result
        # The truncated part should be at most 220 + "…"
        assert long_desc[:220] in result

    def test_apply_link_included_when_present(self):
        from agent.tools.job_search import _format_job_listings
        jobs = [
            {
                "title": "Dev", "company_name": "Co", "location": "NY",
                "description": "Work here.", "job_highlights": [],
                "related_links": [{"link": "https://apply.example.com"}],
            }
        ]
        result = _format_job_listings(jobs)
        assert "https://apply.example.com" in result

    def test_qualifications_extracted_from_highlights(self):
        from agent.tools.job_search import _format_job_listings
        jobs = [
            {
                "title": "Dev", "company_name": "Co", "location": "NY",
                "description": "Work here.",
                "job_highlights": [
                    {
                        "title": "Qualifications",
                        "items": ["5+ years Python", "FastAPI experience"],
                    }
                ],
                "related_links": [],
            }
        ]
        result = _format_job_listings(jobs)
        assert "5+ years Python" in result

    def test_closing_cta_always_present(self):
        from agent.tools.job_search import _format_job_listings
        jobs = [
            {
                "title": "Dev", "company_name": "Co", "location": "NY",
                "description": "Work.", "job_highlights": [], "related_links": [],
            }
        ]
        result = _format_job_listings(jobs)
        assert "cover letter" in result.lower() or "resume" in result.lower()

    def test_multiple_jobs_all_listed(self):
        from agent.tools.job_search import _format_job_listings
        jobs = [
            {"title": f"Job {i}", "company_name": "Co", "location": "NY",
             "description": "Desc.", "job_highlights": [], "related_links": []}
            for i in range(3)
        ]
        result = _format_job_listings(jobs)
        assert "3 job listings" in result
        assert "Job 0" in result
        assert "Job 2" in result


# ── _fetch_jobs_serpapi ───────────────────────────────────────────────────────

class TestFetchJobsSerpapi:
    def test_raises_config_error_when_serpapi_not_installed(self, monkeypatch):
        import builtins
        from exceptions import SerpApiConfigError
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "serpapi":
                raise ImportError("no serpapi")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        from agent.tools.job_search import _call_serpapi
        with pytest.raises(SerpApiConfigError, match="SerpAPI client not installed"):
            _call_serpapi("Python dev", "")

    def test_raises_config_error_when_api_key_missing(self, monkeypatch):
        from exceptions import SerpApiConfigError
        monkeypatch.setenv("SERPAPI_API_KEY", "")
        from agent.tools.job_search import _call_serpapi
        with pytest.raises(SerpApiConfigError, match="SERPAPI_API_KEY"):
            _call_serpapi("Python dev", "")

    def test_returns_jobs_results_list(self):
        fake_jobs = [{"title": "Dev", "company_name": "Co"}]
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"jobs_results": fake_jobs}

        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            result = _call_serpapi("Python developer", "New York")

        assert result == fake_jobs

    def test_location_added_to_params(self):
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"jobs_results": []}

        with patch("serpapi.GoogleSearch", return_value=mock_search) as MockGS:
            from agent.tools.job_search import _call_serpapi
            _call_serpapi("ML Engineer", "San Francisco")

        call_params = MockGS.call_args[0][0]
        assert call_params["location"] == "San Francisco"
        assert "ML Engineer San Francisco" in call_params["q"]

    def test_returns_empty_list_when_no_results(self):
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {}

        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            result = _call_serpapi("Rare Job", "")

        assert result == []

    def test_raises_network_error_on_connection_exception(self):
        from exceptions import SerpApiNetworkError
        mock_search = MagicMock()
        mock_search.get_dict.side_effect = Exception("connection refused")
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiNetworkError):
                _call_serpapi("Dev", "")

    def test_raises_network_error_on_timeout_exception(self):
        from exceptions import SerpApiNetworkError
        mock_search = MagicMock()
        mock_search.get_dict.side_effect = Exception("timeout occurred")
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiNetworkError):
                _call_serpapi("Dev", "")

    def test_raises_serpapi_error_on_generic_exception(self):
        from exceptions import SerpApiError
        mock_search = MagicMock()
        mock_search.get_dict.side_effect = Exception("unexpected server failure")
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiError):
                _call_serpapi("Dev", "")

    def test_raises_rate_limit_error_when_error_dict_has_rate_limit(self):
        from exceptions import SerpApiRateLimitError
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"error": "Rate limit exceeded for this API key"}
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiRateLimitError):
                _call_serpapi("Dev", "")

    def test_raises_config_error_when_error_dict_has_api_key_message(self):
        from exceptions import SerpApiConfigError
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"error": "Invalid API key provided"}
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiConfigError):
                _call_serpapi("Dev", "")

    def test_raises_serpapi_error_on_generic_error_in_response(self):
        from exceptions import SerpApiError
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"error": "Something went wrong on SerpAPI side"}
        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import _call_serpapi
            with pytest.raises(SerpApiError):
                _call_serpapi("Dev", "")


# ── search_jobs (LangChain @tool) ─────────────────────────────────────────────

class TestSearchJobsTool:
    def test_returns_config_error_when_api_key_missing(self, monkeypatch):
        monkeypatch.setenv("SERPAPI_API_KEY", "")
        from agent.tools.job_search import search_jobs
        result = search_jobs.invoke({"query": "Dev", "location": ""})
        assert "Configuration error" in result or "SERPAPI_API_KEY" in result

    def test_returns_formatted_results_on_success(self):
        fake_jobs = [
            {
                "title": "Backend Engineer",
                "company_name": "StartupXYZ",
                "location": "Austin, TX",
                "description": "Build APIs.",
                "job_highlights": [],
                "related_links": [],
            }
        ]
        mock_search = MagicMock()
        mock_search.get_dict.return_value = {"jobs_results": fake_jobs}

        with patch("serpapi.GoogleSearch", return_value=mock_search):
            from agent.tools.job_search import search_jobs
            result = search_jobs.invoke({"query": "Backend Engineer", "location": "Austin"})

        assert "Backend Engineer" in result
        assert "StartupXYZ" in result

    def test_returns_friendly_error_on_exception(self):
        from exceptions import SerpApiError
        with patch("agent.tools.job_search._call_serpapi", side_effect=SerpApiError("boom")):
            from agent.tools.job_search import search_jobs
            result = search_jobs.invoke({"query": "Dev", "location": ""})
        assert "encountered an error" in result.lower() or "job search" in result.lower()

    def test_returns_rate_limit_message_on_rate_limit_error(self):
        from exceptions import SerpApiRateLimitError
        with patch("agent.tools.job_search._call_serpapi", side_effect=SerpApiRateLimitError("quota")):
            from agent.tools.job_search import search_jobs
            result = search_jobs.invoke({"query": "Dev", "location": ""})
        assert "rate limit" in result.lower() or "try again" in result.lower()

    def test_returns_network_message_on_network_error(self):
        from exceptions import SerpApiNetworkError
        with patch("agent.tools.job_search._call_serpapi", side_effect=SerpApiNetworkError("unreachable")):
            from agent.tools.job_search import search_jobs
            result = search_jobs.invoke({"query": "Dev", "location": ""})
        assert "couldn't reach" in result.lower() or "connection" in result.lower() or "check" in result.lower()
