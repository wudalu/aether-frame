# -*- coding: utf-8 -*-
"""Multimodal utilities for ADK framework integration."""

import base64
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def detect_image_mime_type(base64_data: str) -> Optional[str]:
    """
    Detect MIME type from base64 encoded image data.
    
    Args:
        base64_data: Base64 encoded image data
        
    Returns:
        MIME type string or None if not detected
    """
    try:
        # Decode first few bytes to check magic numbers
        header_bytes = base64.b64decode(
            base64_data[:20] + "=="
        )  # Add padding for safety
        
        # Check common image format magic numbers
        if header_bytes.startswith(b'\xff\xd8\xff'):
            return "image/jpeg"
        elif header_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        elif header_bytes.startswith(b'GIF8'):
            return "image/gif"
        elif header_bytes.startswith(b'RIFF') and b'WEBP' in header_bytes[:12]:
            return "image/webp"
        elif header_bytes.startswith(b'BM'):
            return "image/bmp"
        else:
            logger.warning(
                f"Unknown image format, header bytes: {header_bytes[:8].hex()}"
            )
            return None
            
    except Exception as e:
        logger.error(f"Failed to detect MIME type: {str(e)}")
        return None


def decode_base64_image(base64_data: str) -> Optional[bytes]:
    """
    Decode base64 image data to bytes.
    
    Args:
        base64_data: Base64 encoded image data
        
    Returns:
        Decoded image bytes or None if decoding fails
    """
    try:
        # Remove data URL prefix if present (data:image/jpeg;base64,...)
        if base64_data.startswith('data:'):
            base64_data = base64_data.split(',', 1)[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        return image_bytes
        
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {str(e)}")
        return None


def validate_image_format(mime_type: str) -> bool:
    """
    Validate if the image format is supported.
    
    Args:
        mime_type: MIME type string
        
    Returns:
        True if supported, False otherwise
    """
    supported_formats = {
        "image/jpeg",
        "image/jpg", 
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp"
    }
    
    return mime_type.lower() in supported_formats


def extract_base64_from_data_url(data_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract MIME type and base64 data from data URL.
    
    Args:
        data_url: Data URL string (e.g., "data:image/jpeg;base64,/9j/4AAQ...")
        
    Returns:
        Tuple of (mime_type, base64_data) or (None, None) if parsing fails
    """
    try:
        if not data_url.startswith('data:'):
            # Not a data URL, assume it's raw base64
            return None, data_url
            
        # Split data URL: data:image/jpeg;base64,<data>
        header, data = data_url.split(',', 1)
        
        # Extract MIME type from header
        mime_part = header.split(';')[0].replace('data:', '')
        
        return mime_part, data
        
    except Exception as e:
        logger.error(f"Failed to parse data URL: {str(e)}")
        return None, None