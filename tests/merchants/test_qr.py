"""Validate the offline QR encoder against macOS's independent native decoder."""

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
from openagentic.merchants.qr import encode


@pytest.fixture(scope="module")
def native_decoder(tmp_path_factory):
    compiler = shutil.which("swiftc")
    if sys.platform != "darwin" or compiler is None:
        pytest.skip("Independent QR decoding uses the locally installed macOS Vision framework")
    target = tmp_path_factory.mktemp("qr") / "decode"
    source = Path(__file__).resolve().parents[2] / "scripts" / "verify_store_qr_macos.swift"
    subprocess.run(
        [compiler, str(source), "-o", str(target)], check=True, capture_output=True, timeout=60
    )
    return target


def png(matrix):
    # PNG serialization only; the decoder must reconstruct the URL independently.
    scale, quiet = 8, 4
    width = (len(matrix) + quiet * 2) * scale
    rows = []
    for y in range(width):
        row = bytearray([0])
        for x in range(width):
            mx, my = x // scale - quiet, y // scale - quiet
            dark = 0 <= my < len(matrix) and 0 <= mx < len(matrix) and matrix[my][mx]
            row.append(0 if dark else 255)
        rows.append(bytes(row))

    def chunk(kind, data):
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", width, width, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8766/stores/00000000-0000-0000-0000-000000000000",
        "https://example.com/" + "a" * 114,
        "https://本地.example/stores/00000000-0000-0000-0000-000000000000",
    ],
)
def test_native_decoder_recovers_url(native_decoder, tmp_path, url):
    image = tmp_path / "qr.png"
    image.write_bytes(png(encode(url)))
    result = subprocess.run(
        [str(native_decoder), str(image)], check=True, capture_output=True, text=True, timeout=30
    )
    assert result.stdout.strip() == url


def test_long_utf8_payload_rejected():
    with pytest.raises(ValueError):
        encode("商" * 45)
