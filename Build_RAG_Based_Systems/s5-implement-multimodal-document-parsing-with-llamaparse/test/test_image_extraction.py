"""Tests for image extraction and captioning."""
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from main.service.image_extraction import extract_images_from_pdf
from main.service.captioning import generate_caption


class TestImageExtraction:
    """Test image extraction from PDFs."""
    
    @patch("main.service.image_extraction.fitz")
    def test_extract_images_from_pdf(self, mock_fitz):
        """Test extracting images from PDF."""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2  # 2 pages
        
        # Mock page 1 with images
        mock_page1 = MagicMock()
        mock_page1.get_images.return_value = [(1, 0, 0, 0, 0, "RGB", 0, 0, 0, 0)]
        
        # Mock page 2 without images
        mock_page2 = MagicMock()
        mock_page2.get_images.return_value = []
        
        mock_doc.load_page.side_effect = [mock_page1, mock_page2]
        mock_doc.extract_image.return_value = {
            "image": b"fake_image_data",
            "ext": "png"
        }
        
        mock_fitz.open.return_value = mock_doc
        
        with patch("builtins.open", mock_open()) as mock_file:
            images = extract_images_from_pdf("test.pdf", "/tmp")
            
            assert len(images) == 1
            assert images[0]["page"] == 0
            assert images[0]["image_index"] == 0
            mock_doc.close.assert_called_once()
    
    @patch("main.service.image_extraction.fitz")
    def test_extract_no_images(self, mock_fitz):
        """Test PDF with no images."""
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        
        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc.load_page.return_value = mock_page
        
        mock_fitz.open.return_value = mock_doc
        
        images = extract_images_from_pdf("test.pdf", "/tmp")
        
        assert len(images) == 0
        mock_doc.close.assert_called_once()


class TestImageCaptioning:
    """Test image captioning functionality."""
    
    @patch.dict("os.environ", {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        "AZURE_OPENAI_LLM_DEPLOYMENT": "gpt-4o-mini"
    })
    @patch("main.service.captioning.AzureOpenAIClient")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    @patch("main.service.captioning.base64.b64encode")
    def test_generate_caption(self, mock_b64, mock_file, mock_client_class):
        """Test generating image caption."""
        # Mock base64 encoding
        mock_b64.return_value = b"base64_encoded_data"
        
        # Mock Azure OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "A healthy breakfast plate with fruits and oatmeal."
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        caption = generate_caption("test_image.png")
        
        assert caption == "A healthy breakfast plate with fruits and oatmeal."
        mock_client.chat.completions.create.assert_called_once()
    
    @patch.dict("os.environ", {}, clear=True)
    def test_generate_caption_missing_env(self):
        """Test that missing environment variables raise error."""
        with pytest.raises(EnvironmentError):
            generate_caption("test_image.png")
    
    @patch.dict("os.environ", {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        "AZURE_OPENAI_LLM_DEPLOYMENT": "gpt-4o-mini"
    })
    @patch("main.service.captioning.AzureOpenAIClient")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_generate_caption_custom_prompt(self, mock_file, mock_client_class):
        """Test generating caption with custom prompt."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Custom caption"
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        custom_prompt = "Describe this image in detail."
        caption = generate_caption("test_image.png", prompt=custom_prompt)
        
        assert caption == "Custom caption"
        call_args = mock_client.chat.completions.create.call_args
        assert custom_prompt in str(call_args)
