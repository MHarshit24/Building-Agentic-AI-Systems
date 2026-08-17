"""Image Extraction Service Module
Handles image extraction operations from PDF documents.

This module provides:
- Image extraction interface for PDF files
"""
import logging
import os
from typing import List, Dict, Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Extract images from a PDF document.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        
    Returns:
        List of dictionaries containing image information:
        - path: Path to the extracted image file
        - page: Page number (0-indexed)
        - image_index: Index of the image on the page
        
    Returns an empty list if no images are found.
    """
    logger.info(f"Extracting images from PDF: {pdf_path}")
    logger.info(f"Output directory: {output_dir}")

    # TODO: Implement PDF image extraction and return list[dict].
    #
    # HINT:
    # - Open the PDF and iterate through its pages
    # - Detect and extract embedded images
    # - Save each extracted image into `output_dir`
    # - Return a list of dicts with keys: "path", "page", "image_index"
    #
    # Your code here:

    extracted_images = []

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)

    try:
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images()

            for img_index, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    image_data = doc.extract_image(xref)
                    image_bytes = image_data["image"]
                    image_ext = image_data.get("ext", "png")

                    # Build output filename
                    image_filename = f"page{page_num}_img{img_index}.{image_ext}"
                    image_path = os.path.join(output_dir, image_filename)

                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    extracted_images.append({
                        "path": image_path,
                        "page": page_num,
                        "image_index": img_index,
                    })

                    logger.info(f"Extracted image: page={page_num}, index={img_index} -> {image_path}")

                except Exception as img_err:
                    logger.warning(f"Could not extract image page={page_num} index={img_index}: {img_err}")
                    continue
    finally:
        doc.close()

    logger.info(f"Extracted {len(extracted_images)} image(s) from PDF")
    return extracted_images