"""ocr.py with the Mistral API mocked, and its output fed on through extract.py."""
import base64
import io
import json
import sys
import urllib.error

import pytest

import book_model as bm
import extract
import ocr
from conftest import INDEX_HEAD, SUBURBAN_TABLE


# -------------------------------------------------------------------- call
class FakeUrlopen:
    """Answers each request from a script: a dict (JSON) or an HTTP code."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        step = self.script.pop(0)
        if isinstance(step, int):
            raise urllib.error.HTTPError(req.full_url, step, "err", {},
                                         io.BytesIO(b"server says no"))
        return io.BytesIO(json.dumps(step).encode())


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "page-01.png"
    p.write_bytes(b"\x89PNG fake")
    return p


@pytest.fixture
def sleeps(monkeypatch):
    waited = []
    monkeypatch.setattr(ocr.time, "sleep", waited.append)
    return waited


def test_call_sends_image_and_every_setting(monkeypatch, png, sleeps):
    fake = FakeUrlopen({"model": "m", "pages": []})
    monkeypatch.setattr(ocr.urllib.request, "urlopen", fake)
    assert ocr.call("KEY", "mistral-ocr-latest", png) == {"model": "m", "pages": []}
    (req,) = fake.requests
    assert req.full_url == ocr.URL
    assert req.get_header("Authorization") == "Bearer KEY"
    body = json.loads(req.data)
    assert body["model"] == "mistral-ocr-latest"
    assert body["document"]["image_url"] == (
        "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode())
    assert {k: body[k] for k in ocr.SETTINGS} == ocr.SETTINGS
    assert body["include_blocks"] is True       # split_halves needs the boxes
    assert sleeps == []


def test_call_retries_rate_limits_and_server_errors(monkeypatch, png, sleeps):
    monkeypatch.setattr(ocr.urllib.request, "urlopen", FakeUrlopen(429, 502, {"ok": 1}))
    assert ocr.call("K", "m", png) == {"ok": 1}
    assert sleeps == [5, 20]


def test_call_gives_up_after_the_last_retry(monkeypatch, png, sleeps):
    monkeypatch.setattr(ocr.urllib.request, "urlopen", FakeUrlopen(500, 500, 500, 503))
    with pytest.raises(RuntimeError, match="HTTP 503: server says no"):
        ocr.call("K", "m", png)
    assert sleeps == [5, 20, 60]


def test_call_does_not_retry_client_errors(monkeypatch, png, sleeps):
    monkeypatch.setattr(ocr.urllib.request, "urlopen", FakeUrlopen(401))
    with pytest.raises(RuntimeError, match="HTTP 401"):
        ocr.call("K", "m", png)
    assert sleeps == []


# -------------------------------------------------------------------- main
def api_response(png_name):
    """What the API returns for one page: snake_case, one page per call."""
    return {"model": "mistral-ocr-test", "pages": [{
        "index": 0, "dimensions": {"dpi": 200, "width": 1019, "height": 821},
        "blocks": [
            {"type": "header", "content": f"п. № {png_name}", "top_left_x": 40,
             "top_left_y": 10, "bottom_right_x": 150, "bottom_right_y": 22},
            {"type": "table", "content": SUBURBAN_TABLE, "top_left_x": 43,
             "top_left_y": 30, "bottom_right_x": 483, "bottom_right_y": 400},
            {"type": "text", "content": "Примечание.", "top_left_x": 560,
             "top_left_y": 40, "bottom_right_x": 950, "bottom_right_y": 80},
        ]}]}


@pytest.fixture
def renders(tmp_path, monkeypatch):
    """A finished page-renders dir and an index, in a tmp repo root."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "KEY")
    d = tmp_path / "attempts" / "page-renders-00"
    d.mkdir(parents=True)
    for n in (1, 2):
        (d / f"page-{n:02d}.png").write_bytes(b"png")
    (d / "manifest.json").write_text(json.dumps({"source": "sources/book.djvu"}))
    (tmp_path / "attempts" / "index.md").write_text(INDEX_HEAD)
    return d


def run_main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ocr.py", *argv])
    return ocr.main()


def test_main_failed_page_then_resume(renders, monkeypatch, tmp_path):
    calls = []

    def flaky(key, model, png):
        calls.append(png.name)
        if png.name == "page-02.png" and calls.count("page-02.png") == 1:
            raise RuntimeError("HTTP 500")
        return api_response(png.name)

    monkeypatch.setattr(ocr, "call", flaky)
    out = tmp_path / "attempts" / "ocr-00"

    # first run: one page fails, the dir stays unfinished
    assert run_main(monkeypatch, "attempts/page-renders-00") == 1
    assert (out / "page-01.json").exists() and not (out / "page-02.json").exists()
    assert not (out / "manifest.json").exists()
    run = json.loads((out / "run.json").read_text())
    assert run["renders"] == "attempts/page-renders-00" and run["model"] == "mistral-ocr-latest"
    assert "ocr-00" not in (tmp_path / "attempts" / "index.md").read_text()

    # resume: only the missing page is fetched, then the dir is finished
    assert run_main(monkeypatch, "--resume", "attempts/ocr-00") == 0
    assert calls == ["page-01.png", "page-02.png", "page-02.png"]
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["models_reported"] == ["mistral-ocr-test"]
    index = (tmp_path / "attempts" / "index.md").read_text()
    assert "| 00 | book.djvu | page-renders-00 | ocr-00 | – | API, mistral-ocr-test |" in index

    with pytest.raises(SystemExit, match="already finished"):
        run_main(monkeypatch, "--resume", "attempts/ocr-00")


def test_main_refuses_unfinished_renders(renders, monkeypatch):
    (renders / "manifest.json").unlink()
    monkeypatch.setattr(ocr, "call", lambda *a: pytest.fail("no call expected"))
    with pytest.raises(SystemExit, match="no manifest.json"):
        run_main(monkeypatch, "attempts/page-renders-00")


def test_main_needs_the_key(renders, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY")
    with pytest.raises(SystemExit, match="MISTRAL_API_KEY"):
        run_main(monkeypatch, "attempts/page-renders-00")


# ------------------------------------------- ocr.py -> extract.py, end to end
def test_api_output_extracts_to_an_extracted_dir(renders, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ocr, "call", lambda key, model, png: api_response(png.name))
    assert run_main(monkeypatch, "attempts/page-renders-00") == 0

    pages = bm.load_pages(tmp_path / "attempts" / "ocr-00")
    assert len(pages) == 2 and "topLeftX" in pages[0]["blocks"][0]

    monkeypatch.setattr(sys, "argv", ["extract.py", "--src", "attempts/ocr-00",
                                      "--out", "attempts/extracted-00"])
    assert extract.main() == 0
    assert "halves by shape: prose=2, suburban=2" in capsys.readouterr().out

    extracted = tmp_path / "attempts" / "extracted-00"
    text = (extracted / "page-02.md").read_text()
    assert text.startswith("---\nsheet: 2\nkind: spread\nfolios: []\n"
                           "shapes: [suburban, prose]\n---")
    assert "п. № page-02.png" in text and "| Кегумс       | 23.37,5 |" in text
    assert json.loads((extracted / "manifest.json").read_text())["problems"] == 0
    assert "| ocr-00 | extracted-00 |" in (tmp_path / "attempts" / "index.md").read_text()

    # a finished extracted dir is a one-way door
    with pytest.raises(SystemExit, match="already finished"):
        extract.main()
