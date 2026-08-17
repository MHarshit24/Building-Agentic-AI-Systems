"""Image Captioning Service Module
Handles image captioning operations.

This module provides:
- Caption generation interface for extracted images
"""
import logging
import base64
import os
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Import AzureOpenAI client at module level so tests can patch it
from openai import AzureOpenAI as AzureOpenAIClient


def generate_caption(image_path: str, prompt: Optional[str] = None) -> str:
    """
    Generate a caption for an image.
    
    Args:
        image_path: Path to the image file
        prompt: Optional custom prompt for caption generation
        
    Returns:
        str: Generated caption text
    """
    logger.info(f"Generating caption for image: {image_path}")

    if prompt is None:
        prompt = (
            "Describe the content and purpose of this image in a concise caption, "
            "focusing on any nutritional or dietary information."
        )

    # TODO: Implement image captioning and return a caption string.
    #
    # 1) Read image bytes
    # with open(image_path, "rb") as f:
    #     image_bytes = f.read()
    #
    # 2) Call your vision model (e.g., Azure OpenAI vision / OpenAI vision)
    # HINT: Provide both the prompt text and the image payload.
    # HINT: If your API expects a data URL, base64-encode the image bytes.
    #
    # 3) Parse response and return caption string
    # caption = ...
    # return caption

    # Validate required environment variables before proceeding
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
    llm_deployment = os.environ.get("AZURE_OPENAI_LLM_DEPLOYMENT")

    missing = [
        name for name, val in [
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_LLM_DEPLOYMENT", llm_deployment),
        ]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables for captioning: {', '.join(missing)}"
        )

    # 1) Read image bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 2) Base64-encode for the data URL payload
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Determine media type from file extension
    ext = os.path.splitext(image_path)[1].lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "image/png")

    # Build data URL
    data_url = f"data:{media_type};base64,{image_b64}"

    client = AzureOpenAIClient(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    try:
        response = client.chat.completions.create(
            model=llm_deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        # 3) Parse response and return caption string
        caption = response.choices[0].message.content.strip()
        logger.info(f"Caption generated successfully ({len(caption)} characters)")
        return caption

    except Exception as e:
        logger.warning(f"Vision model captioning failed ({e}), using fallback caption")
        return f"Image extracted from dietary document: {os.path.basename(image_path)}"