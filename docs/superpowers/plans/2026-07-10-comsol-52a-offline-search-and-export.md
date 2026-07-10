# COMSOL 5.2a Offline Search and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PDF search tool useful without downloading an embedding model and make solved COMSOL 5.2a models export result data through MCP.

**Architecture:** Keep the existing Chroma semantic search as the preferred implementation when it is already initialized and populated. Add a bounded local lexical fallback that extracts PDF pages with PyMuPDF and returns the same result shape. For exports, resolve the current result dataset and create COMSOL 5.2a-compatible export nodes only when necessary.

**Tech Stack:** Python 3, PyMuPDF, MCP FastMCP, MPh, COMSOL 5.2a Java API, pytest.

---

### Task 1: Offline PDF search

**Files:**
- Modify: `src/knowledge/embedded.py`
- Modify: `tests/test_comsol_compat.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pdf_search_uses_local_fallback_when_vector_store_is_empty(tmp_path, monkeypatch):
    from src.knowledge import embedded

    class FakeProcessor:
        def __init__(self, *_):
            pass

        def get_available_modules(self):
            return [{"name": "Heat_Transfer_Module", "path": str(tmp_path)}]

        def process_pdf(self, path, module):
            return [{"content": "Temperature boundary condition uses T", "source": str(path), "page": 1, "module": module}]

    monkeypatch.setattr(embedded, "PDFProcessor", FakeProcessor)
    monkeypatch.setattr(embedded, "DEFAULT_PDF_DIR", tmp_path)
    monkeypatch.setattr(embedded, "_semantic_pdf_search", lambda *_: None)

    result = embedded.get_pdf_search("temperature boundary", 3)

    assert result["success"] is True
    assert result["backend"] == "local_lexical"
    assert result["count"] == 1
    assert "Temperature" in result["results"][0]["content"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_comsol_compat.py::test_pdf_search_uses_local_fallback_when_vector_store_is_empty -q`

Expected: FAIL because the fallback does not exist.

- [ ] **Step 3: Write the minimal implementation**

```python
def _local_pdf_search(query, n_results, module=None):
    processor = PDFProcessor(DEFAULT_PDF_DIR)
    candidates = _iter_pdf_chunks(processor, module)
    return sorted(candidates, key=lambda item: _keyword_score(query, item["content"]), reverse=True)[:n_results]

def get_pdf_search(query, n_results=5, module=None):
    semantic = _semantic_pdf_search(query, n_results, module)
    if semantic is not None:
        return semantic
    results = _local_pdf_search(query, min(n_results, 20), module)
    return {"success": True, "backend": "local_lexical", "query": query, "results": results, "count": len(results)}
```

The local path must catch an unavailable semantic store, avoid importing SentenceTransformer, search only existing PDF modules, ignore zero-score chunks, and return a clear error only when no readable PDFs exist.

- [ ] **Step 4: Run the focused test and full suite**

Run: `python -m pytest tests/test_comsol_compat.py::test_pdf_search_uses_local_fallback_when_vector_store_is_empty -q` and `python -m pytest -q`

Expected: focused test and all regressions pass.

### Task 2: COMSOL 5.2a export nodes

**Files:**
- Modify: `src/tools/results.py`
- Modify: `tests/test_comsol_compat.py`

- [ ] **Step 1: Write failing unit tests for legacy export-node creation**

```python
def test_legacy_data_export_creates_data_node_for_dataset():
    from src.tools.results import _create_legacy_data_export
    export = FakeExportCollection()
    node = _create_legacy_data_export(export, "data1", "dset1", "C:/tmp/result.txt")
    assert export.calls == [("data1", "Data")]
    assert node.values == [("data", "dset1"), ("filename", "C:/tmp/result.txt")]
```

- [ ] **Step 2: Run each focused test to verify it fails**

Run: `python -m pytest tests/test_comsol_compat.py::test_legacy_data_export_creates_data_node_for_dataset -q`

Expected: FAIL because the helper is absent.

- [ ] **Step 3: Probe the real 5.2a API and implement only supported nodes**

Create a temporary solved 2D heat model through the existing MCP test client. Probe `model.java.result().export().create(tag, type)`, `set("data", dataset)`, `set("filename", path)`, and `run()` for `Data`. The 5.2a standalone session rejects automatic `Image` export creation even when a plot group exists, so retain the existing user-configured image-export path rather than claiming automatic image support.

- [ ] **Step 4: Verify with unit and real MCP tests**

Run: `python -m pytest -q`.

Run the stdio MCP client against a solved 2D heat model and invoke both result export tools. Confirm the generated data file and PNG exist and have nonzero length.

### Task 3: Publish verified work

**Files:**
- Modify: `docs/superpowers/plans/2026-07-10-comsol-52a-offline-search-and-export.md`

- [ ] **Step 1: Run final verification**

Run: `python -m pytest -q`; start the MCP server; confirm `pdf_search`, `pdf_search_status`, `results_export_data`, and `results_export_image` through the stdio protocol; inspect `git diff --check` and `git status --short`.

- [ ] **Step 2: Commit and push**

Run: `git add src/knowledge/embedded.py src/tools/results.py tests/test_comsol_compat.py docs/superpowers/plans/2026-07-10-comsol-52a-offline-search-and-export.md && git commit -m "fix: add offline search and exports for COMSOL 5.2a" && git push origin codex/comsol-52a-base-compat`

Expected: clean local status and pushed fork branch.
