# -*- coding: utf-8 -*-
"""Test ADK multimodal functionality."""

import base64
import pytest
from unittest.mock import MagicMock, patch

from src.aether_frame.agents.adk.adk_event_converter import AdkEventConverter
from src.aether_frame.contracts import ContentPart, ImageReference, UniversalMessage
from src.aether_frame.framework.adk.multimodal_utils import (
    decode_base64_image,
    detect_image_mime_type,
    extract_base64_from_data_url,
    validate_image_format,
)


class TestMultimodalUtils:
    """Test multimodal utility functions."""

    def test_detect_jpeg_mime_type(self):
        """Test JPEG mime type detection."""
        # Create a minimal JPEG header
        jpeg_header = b'\xff\xd8\xff\xe0' + b'\x00' * 10
        base64_jpeg = base64.b64encode(jpeg_header).decode('utf-8')
        
        mime_type = detect_image_mime_type(base64_jpeg)
        assert mime_type == "image/jpeg"

    def test_detect_png_mime_type(self):
        """Test PNG mime type detection."""
        # Create a minimal PNG header
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 10
        base64_png = base64.b64encode(png_header).decode('utf-8')
        
        mime_type = detect_image_mime_type(base64_png)
        assert mime_type == "image/png"

    def test_decode_base64_image(self):
        """Test base64 image decoding."""
        test_data = b"test image data"
        base64_data = base64.b64encode(test_data).decode('utf-8')
        
        decoded = decode_base64_image(base64_data)
        assert decoded == test_data

    def test_decode_data_url_image(self):
        """Test base64 image decoding with data URL prefix."""
        test_data = b"test image data"
        base64_data = base64.b64encode(test_data).decode('utf-8')
        data_url = f"data:image/jpeg;base64,{base64_data}"
        
        decoded = decode_base64_image(data_url)
        assert decoded == test_data

    def test_validate_supported_formats(self):
        """Test validation of supported image formats."""
        assert validate_image_format("image/jpeg") is True
        assert validate_image_format("image/png") is True
        assert validate_image_format("image/webp") is True
        assert validate_image_format("image/gif") is True
        assert validate_image_format("image/bmp") is True
        assert validate_image_format("image/tiff") is False
        assert validate_image_format("application/pdf") is False

    def test_extract_base64_from_data_url(self):
        """Test extracting MIME type and base64 from data URL."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA4GKyH6Q"
        data_url = f"data:image/png;base64,{base64_data}"
        
        mime_type, extracted_data = extract_base64_from_data_url(data_url)
        
        assert mime_type == "image/png"
        assert extracted_data == base64_data

    def test_extract_raw_base64(self):
        """Test handling raw base64 data without data URL prefix."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA4GKyH6Q"
        
        mime_type, extracted_data = extract_base64_from_data_url(base64_data)
        
        assert mime_type is None
        assert extracted_data == base64_data


class TestAdkEventConverter:
    """Test ADK event converter multimodal functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = AdkEventConverter()

    def test_convert_text_message(self):
        """Test converting text-only UniversalMessage to ADK format."""
        message = UniversalMessage(
            role="user",
            content="Hello, how are you?"
        )
        
        result = self.converter.convert_universal_message_to_adk(message)
        
        assert result is not None
        assert result["role"] == "user"
        assert len(result["parts"]) == 1
        assert result["parts"][0]["text"] == "Hello, how are you?"

    def test_convert_multimodal_message_with_text_and_image(self):
        """Test converting multimodal UniversalMessage with text and image."""
        # Create test image data
        test_image_data = b"fake jpeg data"
        base64_image = base64.b64encode(test_image_data).decode('utf-8')
        
        # Create image reference
        image_ref = ImageReference.from_base64(
            base64_data=f"data:image/jpeg;base64,{base64_image}",
            image_format="jpeg"
        )
        
        # Create content parts
        content_parts = [
            ContentPart(text="What do you see in this image?"),
            ContentPart(image_reference=image_ref)
        ]
        
        message = UniversalMessage(
            role="user",
            content=content_parts
        )
        
        result = self.converter.convert_universal_message_to_adk(message)
        
        assert result is not None
        assert result["role"] == "user"
        assert len(result["parts"]) == 2
        
        # Check text part
        text_part = result["parts"][0]
        assert text_part["text"] == "What do you see in this image?"
        
        # Check image part
        image_part = result["parts"][1]
        assert "inline_data" in image_part
        assert image_part["inline_data"]["mime_type"] == "image/jpeg"
        assert image_part["inline_data"]["data"] == test_image_data

    def test_convert_image_only_message(self):
        """Test converting message with only image content."""
        # Create test PNG data
        png_header = b'\x89PNG\r\n\x1a\n' + b'fake png data'
        base64_png = base64.b64encode(png_header).decode('utf-8')
        
        image_ref = ImageReference.from_base64(
            base64_data=base64_png,
            image_format="png"
        )
        
        message = UniversalMessage(
            role="user",
            content=[ContentPart(image_reference=image_ref)]
        )
        
        result = self.converter.convert_universal_message_to_adk(message)
        
        assert result is not None
        assert result["role"] == "user"
        assert len(result["parts"]) == 1
        
        image_part = result["parts"][0]
        assert "inline_data" in image_part
        assert image_part["inline_data"]["mime_type"] == "image/png"
        assert image_part["inline_data"]["data"] == png_header

    def test_convert_invalid_image_reference(self):
        """Test handling of invalid image reference."""
        # Create image reference without base64_data
        image_ref = ImageReference(
            image_path="test.jpg",
            image_format="jpeg",
            metadata={}  # Missing base64_data
        )
        
        message = UniversalMessage(
            role="user",
            content=[ContentPart(image_reference=image_ref)]
        )
        
        result = self.converter.convert_universal_message_to_adk(message)
        
        # Should return message with empty parts since image conversion failed
        assert result is not None
        assert result["role"] == "user"
        assert len(result["parts"]) == 0

    def test_convert_multiple_messages(self):
        """Test converting multiple messages to ADK content."""
        messages = [
            UniversalMessage(role="user", content="First message"),
            UniversalMessage(role="user", content="Second message")
        ]
        
        results = self.converter.convert_universal_messages_to_adk_content(
            messages
        )
        
        assert len(results) == 2
        assert results[0]["parts"][0]["text"] == "First message"
        assert results[1]["parts"][0]["text"] == "Second message"


class TestImageReference:
    """Test ImageReference class functionality."""

    def test_from_base64_class_method(self):
        """Test creating ImageReference from base64 data."""
        base64_data = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ=="
        
        image_ref = ImageReference.from_base64(
            base64_data, image_format="jpeg"
        )
        
        assert image_ref.image_path == ""
        assert image_ref.image_format == "jpeg"
        assert image_ref.metadata["base64_data"] == base64_data

    def test_from_base64_with_metadata(self):
        """Test creating ImageReference with additional metadata."""
        base64_data = "data:image/png;base64,iVBORw0KGgoAAAANSU="
        
        image_ref = ImageReference.from_base64(
            base64_data,
            image_format="png",
            width=100,
            height=200
        )
        
        assert image_ref.metadata["base64_data"] == base64_data
        assert image_ref.metadata["width"] == 100
        assert image_ref.metadata["height"] == 200


if __name__ == "__main__":
    pytest.main([__file__])