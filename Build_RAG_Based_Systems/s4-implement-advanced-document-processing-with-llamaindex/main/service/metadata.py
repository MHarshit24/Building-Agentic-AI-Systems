"""
Metadata Module
Handles document metadata extraction operations.

This module provides:
- Diet-specific metadata assignment based on filename patterns
"""

import os
import logging

logger = logging.getLogger(__name__)


def get_file_metadata(file_path):
    """
    Extract metadata from file path based on filename for diet counselling context.
    
    Metadata categories:
    - meal_type: breakfast, lunch, dinner, snack
    - dietary_restriction: vegetarian, vegan, gluten-free, keto, diabetic, low-sodium
    - nutrition_category: protein, carbohydrates, vitamins, minerals, healthy-fats
    - topic: meal-planning, recipes, nutrition-facts, dietary-guidelines
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with metadata (source filename and diet-specific attributes)
    """
    filename = os.path.basename(file_path).lower()
    metadata = {"source": os.path.basename(file_path)}
    
    # Meal type detection
    if any(keyword in filename for keyword in ["breakfast", "morning", "am"]):
        metadata["meal_type"] = "breakfast"
    elif any(keyword in filename for keyword in ["lunch", "midday", "noon"]):
        metadata["meal_type"] = "lunch"
    elif any(keyword in filename for keyword in ["dinner", "evening", "supper"]):
        metadata["meal_type"] = "dinner"
    elif any(keyword in filename for keyword in ["snack", "between-meals"]):
        metadata["meal_type"] = "snack"
    
    # Dietary restriction detection
    if "vegetarian" in filename:
        metadata["dietary_restriction"] = "vegetarian"
    elif "vegan" in filename:
        metadata["dietary_restriction"] = "vegan"
    elif "gluten" in filename or "gluten-free" in filename:
        metadata["dietary_restriction"] = "gluten-free"
    elif "keto" in filename:
        metadata["dietary_restriction"] = "keto"
    elif "diabetic" in filename or "diabetes" in filename:
        metadata["dietary_restriction"] = "diabetic"
    elif "low-sodium" in filename or "low_sodium" in filename or "sodium" in filename:
        metadata["dietary_restriction"] = "low-sodium"
    
    # Nutrition category detection
    if "protein" in filename:
        metadata["nutrition_category"] = "protein"
    elif "carb" in filename or "carbohydrate" in filename:
        metadata["nutrition_category"] = "carbohydrates"
    elif "vitamin" in filename:
        metadata["nutrition_category"] = "vitamins"
    elif "mineral" in filename:
        metadata["nutrition_category"] = "minerals"
    elif "fat" in filename or "omega" in filename:
        metadata["nutrition_category"] = "healthy-fats"
    
    # Topic detection
    if "recipe" in filename or "recipes" in filename:
        metadata["topic"] = "recipes"
    elif "meal" in filename or "planning" in filename:
        metadata["topic"] = "meal-planning"
    elif "nutrition" in filename or "nutrient" in filename:
        metadata["topic"] = "nutrition-facts"
    elif "guideline" in filename or "guide" in filename:
        metadata["topic"] = "dietary-guidelines"
    
    return metadata

