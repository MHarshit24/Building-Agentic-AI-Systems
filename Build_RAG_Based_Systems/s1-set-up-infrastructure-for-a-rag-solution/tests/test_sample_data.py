"""
Tests for sample data module.
"""

import os
import sys

# Add parent directory to path to import main modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main.sample_data import SAMPLE_SENTENCES


class TestSampleData:
    """Test sample data constants."""

    def test_sample_sentences_is_list(self):
        """Test that SAMPLE_SENTENCES is a list."""
        assert isinstance(SAMPLE_SENTENCES, list)

    def test_sample_sentences_not_empty(self):
        """Test that SAMPLE_SENTENCES is not empty."""
        assert len(SAMPLE_SENTENCES) > 0

    def test_sample_sentences_all_strings(self):
        """Test that all items in SAMPLE_SENTENCES are strings."""
        assert all(isinstance(sentence, str) for sentence in SAMPLE_SENTENCES)

    def test_sample_sentences_not_empty_strings(self):
        """Test that all sentences are non-empty."""
        assert all(len(sentence.strip()) > 0 for sentence in SAMPLE_SENTENCES)

    def test_sample_sentences_automotive_content(self):
        """Test that sample sentences contain automotive-related content."""
        content = " ".join(SAMPLE_SENTENCES).lower()
        automotive_keywords = ["engine", "sensor", "brake", "transmission", "calibration"]
        assert any(keyword in content for keyword in automotive_keywords)

    def test_sample_sentences_count(self):
        """Test that we have the expected number of sample sentences."""
        assert len(SAMPLE_SENTENCES) == 5

