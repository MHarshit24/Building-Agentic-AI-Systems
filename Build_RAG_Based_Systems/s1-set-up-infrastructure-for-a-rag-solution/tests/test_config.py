"""
Tests for configuration and logging setup.
"""

import os
import logging
import pytest
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import main modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main.config import setup_logging, load_config


class TestSetupLogging:
    """Test logging configuration."""

    def test_setup_logging_default_level(self):
        """Test that logging is set up with default INFO level."""
        setup_logging()
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_custom_level(self):
        """Test that logging can be set up with custom level."""
        setup_logging(level=logging.DEBUG)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_handlers(self):
        """Test that logging has console handler."""
        setup_logging()
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        assert len(handlers) > 0
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_setup_logging_suppresses_noisy_loggers(self):
        """Test that noisy loggers are suppressed."""
        setup_logging()
        urllib3_logger = logging.getLogger("urllib3")
        openai_logger = logging.getLogger("openai")
        assert urllib3_logger.level >= logging.WARNING
        assert openai_logger.level >= logging.WARNING


class TestLoadConfig:
    """Test configuration loading."""

    @patch("main.config.load_dotenv")
    def test_load_config_success(self, mock_load_dotenv, mock_env_vars):
        """Test successful configuration loading with all required variables."""
        mock_load_dotenv.return_value = None
        config = load_config()
        
        assert config["database_url"] == "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"
        assert config["azure_endpoint"] == "https://test.openai.azure.com/"
        assert config["azure_api_key"] == "test-api-key"
        assert config["azure_embedding_deployment"] == "text-embedding-3-small"
        assert config["api_version"] == "2024-02-01"
        assert config["collection_name"] == "test_collection"

    @patch("main.config.load_dotenv")
    def test_load_config_missing_api_key(self, mock_load_dotenv, monkeypatch):
        """Test that missing API key raises ValueError."""
        mock_load_dotenv.return_value = None
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            load_config()

    @patch("main.config.load_dotenv")
    def test_load_config_missing_endpoint(self, mock_load_dotenv, monkeypatch):
        """Test that missing endpoint raises ValueError."""
        mock_load_dotenv.return_value = None
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            load_config()

    @patch("main.config.load_dotenv")
    def test_load_config_missing_deployment(self, mock_load_dotenv, monkeypatch):
        """Test that missing deployment raises ValueError."""
        mock_load_dotenv.return_value = None
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            load_config()

    @patch("main.config.load_dotenv")
    def test_load_config_default_api_version(self, mock_load_dotenv, monkeypatch):
        """Test that default API version is used when not provided."""
        mock_load_dotenv.return_value = None
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        
        config = load_config()
        assert config["api_version"] == "2024-02-01"

    @patch("main.config.load_dotenv")
    def test_load_config_default_collection_name(self, mock_load_dotenv, monkeypatch):
        """Test that default collection name is used when not provided."""
        mock_load_dotenv.return_value = None
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
        monkeypatch.delenv("COLLECTION_NAME", raising=False)
        
        config = load_config()
        assert config["collection_name"] == "automind_embedding"

