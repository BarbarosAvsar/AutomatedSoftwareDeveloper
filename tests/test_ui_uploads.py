from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.ui.image_to_requirements import image_to_requirements
from automated_software_developer.agent.ui.requirements_assistant import parse_requirements_upload
from automated_software_developer.agent.ui.voice_input_handler import VoiceInputHandler


def _build_pdf(text: str) -> bytes:
    header = b"%PDF-1.4\n"
    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects.append(
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content
        + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    offsets = []
    body = b""
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_offset = len(header) + len(body)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n"
    trailer += f"{xref_offset}\n%%EOF\n".encode("ascii")
    return header + body + b"".join(xref) + trailer


def test_parse_requirements_upload_md() -> None:
    content = b"# Requirements\n- item"
    text = parse_requirements_upload("spec.md", content)
    assert "Requirements" in text


def test_parse_requirements_upload_pdf() -> None:
    payload = _build_pdf("Hello AEC")
    text = parse_requirements_upload("spec.pdf", payload)
    assert "Hello AEC" in text


def test_voice_input_handler_opt_in() -> None:
    handler = VoiceInputHandler()
    try:
        handler.ingest_transcript(session_id="s1", transcript="Test")
    except ValueError as exc:
        assert "disabled" in str(exc).lower()

    handler = VoiceInputHandler(allow_server_side=True)
    transcript = handler.ingest_transcript(session_id="s1", transcript="Launch now")
    assert transcript.transcript == "Launch now"


def test_image_to_requirements(tmp_path: Path) -> None:
    image_path = tmp_path / "dashboard.png"
    image_path.write_bytes(b"")
    addendum = image_to_requirements(image_path)
    assert "Dashboard" in addendum.screens
