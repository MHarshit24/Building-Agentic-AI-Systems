"""Tests for table extraction and processing."""
import pytest
from unittest.mock import MagicMock, patch

from main.service.table_extraction import find_markdown_tables
from main.service.table_processing import summarize_table, build_nodes_from_tables
from llama_index.core.schema import TextNode


class TestTableExtraction:
    """Test table extraction from markdown."""
    
    def test_find_simple_table(self):
        """Test finding a simple markdown table."""
        text = """
Some text before the table.

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
| Value 3  | Value 4  |

Some text after the table.
"""
        tables = find_markdown_tables(text)
        assert len(tables) == 1
        assert "Column 1" in tables[0][2]
        assert "Value 1" in tables[0][2]
    
    def test_find_multiple_tables(self):
        """Test finding multiple tables."""
        text = """
| Table 1 Col1 | Table 1 Col2 |
|--------------|--------------|
| Value 1      | Value 2      |

| Table 2 Col1 | Table 2 Col2 |
|--------------|--------------|
| Value 3      | Value 4      |
"""
        tables = find_markdown_tables(text)
        assert len(tables) == 2
    
    def test_find_no_tables(self):
        """Test text with no tables."""
        text = "This is just regular text with no tables."
        tables = find_markdown_tables(text)
        assert len(tables) == 0
    
    def test_table_with_separator_variations(self):
        """Test table with different separator styles."""
        text = """
| Header 1 | Header 2 |
|:---------|:--------:|
| Data 1   | Data 2   |
"""
        tables = find_markdown_tables(text)
        assert len(tables) == 1


class TestTableProcessing:
    """Test table processing and summarization."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        mock = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This table contains nutritional information about breakfast items."
        mock.complete.return_value = mock_response
        return mock
    
    def test_summarize_table(self, mock_llm):
        """Test table summarization."""
        table_md = """
| Food | Calories | Protein |
|------|----------|---------|
| Eggs | 70      | 6g      |
| Oats | 150     | 5g      |
"""
        summary = summarize_table(mock_llm, table_md)
        
        assert summary is not None
        assert len(summary) > 0
        mock_llm.complete.assert_called_once()
    
    def test_summarize_table_content_filter(self, mock_llm):
        """Test table summarization with content filter fallback."""
        # Simulate content filter error
        mock_llm.complete.side_effect = Exception("content_filter triggered")
        
        table_md = """
| Food | Calories |
|------|----------|
| Eggs | 70      |
"""
        summary = summarize_table(mock_llm, table_md)
        
        assert summary is not None
        assert "Table" in summary
    
    def test_build_nodes_from_tables(self, mock_llm):
        """Test building nodes from tables."""
        table_markdowns = [
            "| Food | Calories |\n|------|----------|\n| Eggs | 70      |",
            "| Food | Protein |\n|------|--------|\n| Oats | 5g     |"
        ]
        
        metadata = {
            "source": "breakfast_recipes.pdf",
            "meal_type": "breakfast"
        }
        
        nodes = build_nodes_from_tables(
            source_name="breakfast_recipes.pdf",
            table_markdowns=table_markdowns,
            llm=mock_llm,
            additional_metadata=metadata
        )
        
        assert len(nodes) == 2
        assert all(isinstance(node, TextNode) for node in nodes)
        assert all(node.metadata["content_type"] == "table_summary" for node in nodes)
        assert all(node.metadata["source"] == "breakfast_recipes.pdf" for node in nodes)
        assert all(node.metadata["meal_type"] == "breakfast" for node in nodes)
        assert nodes[0].metadata["table_index"] == 0
        assert nodes[1].metadata["table_index"] == 1
