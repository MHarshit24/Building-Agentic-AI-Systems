"""Metadata Service Module
Handles diet-specific metadata extraction from filenames and file paths.

This module provides:
- Diet metadata extraction from filenames
- File metadata construction (source, extension, size, tags)
"""

import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Diet-specific metadata categories
MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
DIETARY_RESTRICTIONS = ["vegetarian", "vegan", "gluten-free", "keto", "diabetic", "low-sodium"]
NUTRITION_CATEGORIES = ["protein", "carbohydrates", "vitamins", "minerals", "healthy-fats"]
TOPICS = ["recipes", "meal-planning", "nutrition-facts", "dietary-guidelines"]


def extract_diet_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """
    Extract diet-specific metadata from filename.

    Automatically assigns metadata based on filename patterns:
    - Meal types: breakfast, lunch, dinner, snack
    - Dietary restrictions: vegetarian, vegan, gluten-free, keto, diabetic, low-sodium
    - Nutrition categories: protein, carbohydrates, vitamins, minerals, healthy-fats
    - Topics: recipes, meal-planning, nutrition-facts, dietary-guidelines

    Args:
        filename: Name of the file (without path)

    Returns:
        Dictionary containing extracted diet metadata
    """
    filename_lower = filename.lower()
    metadata: Dict[str, Any] = {}

    # Extract meal type
    for meal_type in MEAL_TYPES:
        if meal_type in filename_lower:
            metadata["meal_type"] = meal_type
            break

    # Extract dietary restriction
    for restriction in DIETARY_RESTRICTIONS:
        if restriction in filename_lower or restriction.replace("-", "_") in filename_lower:
            metadata["dietary_restriction"] = restriction
            break

    # Extract nutrition category
    for category in NUTRITION_CATEGORIES:
        if category in filename_lower or category.replace("-", "_") in filename_lower:
            metadata["nutrition_category"] = category
            break

    # Extract topic
    for topic in TOPICS:
        if topic in filename_lower or topic.replace("-", "_") in filename_lower:
            metadata["topic"] = topic
            break

    logger.debug(f"Extracted diet metadata from '{filename}': {metadata}")
    return metadata


def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a file including diet-specific metadata.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary containing file metadata and diet-specific tags
    """
    path = Path(file_path)
    filename = path.name

    # Base file metadata
    metadata: Dict[str, Any] = {
        "source": filename,
        "file_path": str(path),
        "file_extension": path.suffix.lower(),
        "file_size": path.stat().st_size if path.exists() else 0,
    }

    # Extract diet-specific metadata from filename
    diet_metadata = extract_diet_metadata_from_filename(filename)
    metadata.update(diet_metadata)

    return metadata


