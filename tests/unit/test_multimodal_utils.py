# -*- coding: utf-8 -*-
"""Unit tests for multimodal utility helpers."""

import base64

from aether_frame.framework.adk import multimodal_utils as mm


def test_detect_image_mime_type_known_formats():
    jpeg_bytes = b"\xff\xd8\xff\xdb"
    encoded = base64.b64encode(jpeg_bytes).decode("utf-8")
    assert mm.detect_image_mime_type(encoded) == "image/jpeg"

    png_bytes = b"\x89PNG\r\n\x1a\nrest"
    encoded = base64.b64encode(png_bytes).decode("utf-8")
    assert mm.detect_image_mime_type(encoded) == "image/png"


def test_detect_image_mime_type_unknown_logs_and_returns_none(caplog):
    data = base64.b64encode(b"XYZ").decode("utf-8")
    assert mm.detect_image_mime_type(data) is None
    assert "Unknown image format" in caplog.text


def test_decode_base64_image_handles_data_url():
    content = base64.b64encode(b"hello").decode("utf-8")
    data_url = f"data:image/png;base64,{content}"
    assert mm.decode_base64_image(data_url) == b"hello"
    assert mm.decode_base64_image("not-base64") is None


def test_validate_image_format_case_insensitive():
    assert mm.validate_image_format("IMAGE/PNG") is True
    assert mm.validate_image_format("image/svg") is False


def test_extract_base64_from_data_url_and_raw():
    data_url = "data:image/jpeg;base64,abcd1234"
    mime, data = mm.extract_base64_from_data_url(data_url)
    assert mime == "image/jpeg"
    assert data == "abcd1234"

    mime, data = mm.extract_base64_from_data_url("YWJjZA==")
    assert mime is None
    assert data == "YWJjZA=="
