# -*- coding: utf-8 -*-
"""Unit tests for ADK multimodal utility helpers."""

import base64

from aether_frame.framework.adk import multimodal_utils as utils


def test_detect_image_mime_type_for_known_formats(monkeypatch):
    jpeg_bytes = b"\xff\xd8\xff\xf0"
    data = base64.b64encode(jpeg_bytes).decode()
    assert utils.detect_image_mime_type(data) == "image/jpeg"

    png_data = base64.b64encode(b"\x89PNG\r\n\x1a\nrest").decode()
    assert utils.detect_image_mime_type(png_data) == "image/png"


def test_decode_base64_image_handles_prefix():
    raw_bytes = b"binarydata"
    base64_data = base64.b64encode(raw_bytes).decode()
    assert utils.decode_base64_image(base64_data) == raw_bytes

    data_url = f"data:image/png;base64,{base64_data}"
    assert utils.decode_base64_image(data_url) == raw_bytes


def test_validate_image_format_and_extract_data_url():
    assert utils.validate_image_format("image/jpeg") is True
    assert utils.validate_image_format("IMAGE/PNG") is True
    assert utils.validate_image_format("image/tiff") is False

    mime, payload = utils.extract_base64_from_data_url("data:image/gif;base64,AAA=")
    assert mime == "image/gif"
    assert payload == "AAA="

    raw = "Zm9v"
    mime2, payload2 = utils.extract_base64_from_data_url(raw)
    assert mime2 is None
    assert payload2 == raw
