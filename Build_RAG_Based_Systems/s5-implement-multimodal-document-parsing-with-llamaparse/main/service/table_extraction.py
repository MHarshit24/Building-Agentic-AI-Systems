"""Table Extraction Service Module
Handles table extraction operations from markdown text.

This module provides:
- Markdown table extraction interface
"""
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def find_markdown_tables(md_text: str) -> List[Tuple[int, int, str]]:
    """
    Extract markdown table blocks from text.

    Returns a list of tuples: (start_index, end_index, table_string)
    
    Args:
        md_text: Markdown text to search for tables
        
    Returns:
        List of tuples containing (start_char_index, end_char_index, table_markdown)
    """
    logger.info("Extracting markdown tables (boilerplate)")

    # TODO: Find and extract markdown table blocks from `md_text`.
    # HINT: Split text into lines and identify contiguous blocks that represent a table.
    # HINT: For each detected table block, return a tuple of:
    #   - start_char_index (in the original string)
    #   - end_char_index (in the original string)
    #   - table_markdown (the exact markdown table text)
    # HINT: Return an empty list if no tables exist.
    # Your code here:
    tables = []

    lines = md_text.splitlines(keepends=True)

    # Track character offset as we walk through lines
    char_offset = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # A markdown table line contains at least one '|'
        if "|" in stripped:
            # Start of a potential table block
            table_start_char = char_offset
            table_lines = []

            # Collect all contiguous lines that look like table rows
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                char_offset += len(lines[i])
                i += 1

            # A valid markdown table must have at least 2 lines
            # (header row + separator row)
            if len(table_lines) >= 2:
                # Verify second line is a separator (contains dashes)
                separator = table_lines[1].strip()
                if all(c in "-|: " for c in separator) and "-" in separator:
                    table_markdown = "".join(table_lines)
                    table_end_char = table_start_char + len(table_markdown)
                    tables.append((table_start_char, table_end_char, table_markdown))
        else:
            char_offset += len(line)
            i += 1

    logger.info(f"Found {len(tables)} markdown table(s)")
    return tables