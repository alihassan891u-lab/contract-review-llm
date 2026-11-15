import json

import pytest

from contractlens.cli import main
from contractlens.report import to_html, to_markdown


def test_cli_review_json(risky_path, capsys):
    assert main(["review", str(risky_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["overall_risk"] == "critical"


def test_cli_fail_on(risky_path, nda_path):
    assert main(["review", str(risky_path), "--fail-on", "high"]) == 2
    assert main(["review", str(nda_path), "--fail-on", "low"]) == 0


def test_cli_ask(risky_path, capsys):
    assert main(["ask", str(risky_path), "Can they raise prices?"]) == 0
    assert "increase the fees" in capsys.readouterr().out


def test_reports_render(risky_report):
    html = to_html(risky_report)
    assert html.startswith("<!DOCTYPE html>") and "Unlimited or uncapped liability" in html
    assert "<script" not in html  # contract text is escaped, never executed
    md = to_markdown(risky_report)
    assert "## Critical risk (1)" in md


def test_api_roundtrip(risky_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from contractlens.api import app

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    r = client.post("/review", files={"file": (risky_path.name, risky_path.read_bytes(), "text/plain")})
    assert r.status_code == 200
    rid = r.json()["review_id"]
    a = client.post(f"/reviews/{rid}/ask", json={"question": "Can they raise prices?"}).json()
    assert a["grounded"]
    assert client.get(f"/reviews/{rid}/report.html").status_code == 200
    assert client.post("/review", files={"file": ("x.xls", b"abc", "application/octet-stream")}).status_code == 422
