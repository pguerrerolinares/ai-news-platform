# Pipeline Quality Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix GitHub extractor returning 0 results, filter HuggingFace model repo pages from news, expand variant collapse, and clean existing bad data from production DB.

**Architecture:** Tag-based filtering at extraction time using HuggingFace API metadata (`base_model:quantized:*` tags, `library_name`, `createdAt`). Expanded variant collapse as safety net. One-char fix for GitHub date query.

**Tech Stack:** Python 3.12+, httpx, respx (tests), PostgreSQL (cleanup)

---

### Task 1: Fix GitHub `pushed:>` → `pushed:>=`

**Files:**
- Modify: `src/extractors/github.py:86`
- Modify: `tests/unit/test_github_extractor.py`

**Step 1: Write a failing test that verifies the query uses `>=`**

Add to `tests/unit/test_github_extractor.py` class `TestExtract`:

```python
@respx.mock
async def test_search_query_uses_gte_for_pushed_date(self):
    """Verify pushed: uses >= (not >) to include today's repos."""
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
    with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
        await GitHubExtractor().extract()
    request = respx.calls.last.request
    query_param = str(request.url.params.get("q", ""))
    assert "pushed:>=" in query_param, f"Expected pushed:>= but got: {query_param}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_github_extractor.py::TestExtract::test_search_query_uses_gte_for_pushed_date -v`
Expected: FAIL — query contains `pushed:>` not `pushed:>=`

**Step 3: Fix the one character**

In `src/extractors/github.py:86`, change:
```python
q = f"{query} stars:>{min_stars} pushed:>{since_date}"
```
to:
```python
q = f"{query} stars:>{min_stars} pushed:>={since_date}"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_github_extractor.py::TestExtract::test_search_query_uses_gte_for_pushed_date -v`
Expected: PASS

**Step 5: Run all GitHub extractor tests**

Run: `pytest tests/unit/test_github_extractor.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/extractors/github.py tests/unit/test_github_extractor.py
git commit -m "fix: GitHub extractor pushed:> → pushed:>= to include today's repos"
```

---

### Task 2: Filter quantized/re-upload models in HuggingFace extractor

**Files:**
- Modify: `src/extractors/huggingface.py`
- Modify: `tests/unit/test_huggingface_extractor.py`

**Step 1: Write failing tests for quantization tag filtering**

Add to `tests/unit/test_huggingface_extractor.py`. First update `_make_model` to support `library_name` and `created_at`:

```python
def _make_model(
    model_id: str = "meta-llama/Llama-3-8B",
    author: str = "meta-llama",
    downloads: int = 50000,
    likes: int = 1200,
    pipeline_tag: str = "text-generation",
    tags: list[str] | None = None,
    last_modified: str | None = None,
    card_data: dict | None = None,
    library_name: str | None = "transformers",
    created_at: str | None = None,
) -> dict:
    result = {
        "modelId": model_id,
        "id": model_id,
        "author": author,
        "downloads": downloads,
        "likes": likes,
        "pipeline_tag": pipeline_tag,
        "tags": tags or ["text-generation", "pytorch"],
        "lastModified": last_modified or _recent_iso(),
        "cardData": card_data,
    }
    if library_name is not None:
        result["library_name"] = library_name
    if created_at is not None:
        result["createdAt"] = created_at
    return result
```

Then add new test class:

```python
class TestQuantizationFiltering:
    """Tests for filtering quantized/re-upload models."""

    @respx.mock
    async def test_skips_model_with_quantized_tag(self):
        """Models with base_model:quantized:* tag should be filtered out."""
        original = _make_model("Qwen/Qwen3.5-35B-A3B", downloads=5000, tags=[
            "transformers", "safetensors",
            "base_model:Qwen/Qwen3.5-35B-A3B-Base",
        ])
        quantized = _make_model("unsloth/Qwen3.5-35B-A3B-GGUF", downloads=6000, tags=[
            "gguf", "base_model:Qwen/Qwen3.5-35B-A3B",
            "base_model:quantized:Qwen/Qwen3.5-35B-A3B",
        ], library_name=None)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[original, quantized]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        titles = [item.title for item in result]
        assert "Qwen/Qwen3.5-35B-A3B" in titles
        assert "unsloth/Qwen3.5-35B-A3B-GGUF" not in titles

    @respx.mock
    async def test_skips_model_without_library_name(self):
        """Models with library_name=None are likely quantization wrappers."""
        model = _make_model("unsloth/Model-GGUF", downloads=5000, library_name=None)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 0

    @respx.mock
    async def test_keeps_model_with_library_and_no_quantized_tag(self):
        """Original models with library_name should pass through."""
        model = _make_model("Qwen/Qwen3.5-35B", downloads=5000, library_name="transformers", tags=[
            "transformers", "safetensors",
        ])
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_daily_papers_not_affected_by_filter(self):
        """Daily papers should pass through regardless of filtering."""
        quantized = _make_model("unsloth/Model-GGUF", downloads=5000, library_name=None)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[quantized]))
        papers = [_make_daily_paper("Cool Paper", "2401.00001", upvotes=50)]
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=papers))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].title == "Cool Paper"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_huggingface_extractor.py::TestQuantizationFiltering -v`
Expected: FAIL — quantized models currently pass through

**Step 3: Implement filtering in extractor**

In `src/extractors/huggingface.py`, add helper function and modify the model loop:

```python
def _is_quantized_reupload(model: dict) -> bool:
    """Check if a model is a quantization/re-upload based on HF API metadata."""
    tags = model.get("tags", [])
    if any(tag.startswith("base_model:quantized:") for tag in tags):
        return True
    if model.get("library_name") is None:
        return True
    return False
```

In the `extract()` method, after the `downloads < min_downloads` check, add:

```python
if _is_quantized_reupload(model):
    continue
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_huggingface_extractor.py::TestQuantizationFiltering -v`
Expected: All PASS

**Step 5: Run all HuggingFace extractor tests**

Run: `pytest tests/unit/test_huggingface_extractor.py -v`
Expected: All pass. Some existing tests may need `library_name` added to `_make_model` calls if they now get filtered.

**Step 6: Commit**

```bash
git add src/extractors/huggingface.py tests/unit/test_huggingface_extractor.py
git commit -m "fix: filter quantized/re-upload HuggingFace models using API tags"
```

---

### Task 3: Expand variant collapse suffixes and size normalization

**Files:**
- Modify: `src/feed/variant_collapse.py`
- Modify: `tests/unit/test_variant_collapse.py`

**Step 1: Write failing tests for new suffixes and size normalization**

Add to `tests/unit/test_variant_collapse.py` class `TestNormalizeModelName`:

```python
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("nvidia/Qwen3.5-27B-FP8", "qwen3.5-27b"),
        ("user/Model-FP16", "model"),
        ("nvidia/Model-NVFP4", "model"),
        ("huihui-ai/Model-abliterated", "model"),
        ("user/Model-censored", "model"),
    ],
)
def test_strips_extended_suffixes(self, title: str, expected: str) -> None:
    assert normalize_model_name(title) == expected
```

Add new test class for size normalization:

```python
class TestSizeNormalization:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Qwen/Qwen3.5-0.8B", "qwen3.5"),
            ("Qwen/Qwen3.5-27B", "qwen3.5"),
            ("Qwen/Qwen3.5-397B-A17B", "qwen3.5"),
            ("Qwen/Qwen3.5-35B-A3B", "qwen3.5"),
            ("meta-llama/Llama-3-8B", "llama-3"),
            ("meta-llama/Llama-3-70B", "llama-3"),
        ],
    )
    def test_normalizes_parameter_size(self, title: str, expected: str) -> None:
        assert normalize_model_name(title) == expected
```

Add collapse test:

```python
class TestCollapseVariantsSizeNormalization:
    def test_collapses_different_sizes_same_family(self) -> None:
        small = _make_item(source="huggingface", title="Qwen/Qwen3.5-0.8B", score=100)
        large = _make_item(source="huggingface", title="Qwen/Qwen3.5-27B", score=200)
        result = collapse_variants([small, large])
        assert len(result) == 1
        assert result[0] is large
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_variant_collapse.py::TestNormalizeModelName::test_strips_extended_suffixes tests/unit/test_variant_collapse.py::TestSizeNormalization tests/unit/test_variant_collapse.py::TestCollapseVariantsSizeNormalization -v`
Expected: FAIL

**Step 3: Implement expanded suffixes and size normalization**

In `src/feed/variant_collapse.py`:

```python
# Known quantization/format suffixes to strip
_SUFFIXES = re.compile(
    r"-(GGUF|GPTQ|AWQ|ONNX|EXL2|MLX|FP8|FP16|NVFP4|abliterated|censored)$",
    re.IGNORECASE,
)

# Parameter size pattern: -0.8B, -27B, -397B-A17B, etc.
_PARAM_SIZE = re.compile(r"-\d+\.?\d*B(-A\d+\.?\d*B)?", re.IGNORECASE)
```

Update `normalize_model_name`:

```python
def normalize_model_name(title: str) -> str | None:
    """Extract normalized base model name from a HuggingFace title."""
    if "/" not in title:
        return None

    org, model = title.split("/", 1)

    # Strip quantization suffix
    model = _SUFFIXES.sub("", model)

    # Strip parameter size
    model = _PARAM_SIZE.sub("", model)

    return model.lower()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_variant_collapse.py -v`
Expected: All pass

**IMPORTANT:** Check that existing tests like `test_preserves_original_model_names` still pass. The size normalization will change expected values:
- `"meta-llama/Llama-2-7B"` → was `"llama-2-7b"`, now `"llama-2"` (size stripped)
- `"mistralai/Mistral-7B-v0.1"` → was `"mistral-7b-v0.1"`, now `"mistral-v0.1"` (size stripped)
- `"google/gemma-2b"` → was `"gemma-2b"`, now `"gemma"` (size stripped)

Update existing parametrized expected values accordingly. Also update `test_keeps_original_drops_gguf_variant` and `test_does_not_collapse_different_models` expected values since Llama-2-7B and Mistral-7B will now normalize to `llama-2` and `mistral`.

**Step 5: Commit**

```bash
git add src/feed/variant_collapse.py tests/unit/test_variant_collapse.py
git commit -m "feat: expand variant collapse with FP8/abliterated suffixes and size normalization"
```

---

### Task 4: Improve HuggingFace ExtractedItem text field

**Files:**
- Modify: `src/extractors/huggingface.py`
- Modify: `tests/unit/test_huggingface_extractor.py`

**Step 1: Write failing test for improved text**

```python
class TestImprovedModelText:
    @respx.mock
    async def test_text_includes_pipeline_tag(self):
        """text field should include pipeline_tag for better classifier context."""
        model = _make_model(
            "org/model-x", downloads=5000,
            pipeline_tag="text-generation",
            tags=["transformers", "safetensors", "text-generation"],
            library_name="transformers",
        )
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].text != result[0].title, "text should not just repeat title"
        assert "text-generation" in result[0].text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_huggingface_extractor.py::TestImprovedModelText -v`
Expected: FAIL — currently `text=model_id`

**Step 3: Implement improved text**

In `src/extractors/huggingface.py`, change the `ExtractedItem` construction in the model loop. Replace:
```python
text=model_id,
```
with:
```python
text=self._build_model_text(model_id, model),
```

Add helper method to `HuggingFaceExtractor`:
```python
@staticmethod
def _build_model_text(model_id: str, model: dict) -> str:
    """Build descriptive text from model metadata for the classifier."""
    parts = [model_id]
    pipeline_tag = model.get("pipeline_tag")
    if pipeline_tag:
        parts.append(f"Task: {pipeline_tag}")
    library = model.get("library_name")
    if library:
        parts.append(f"Library: {library}")
    return " | ".join(parts)
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_huggingface_extractor.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/extractors/huggingface.py tests/unit/test_huggingface_extractor.py
git commit -m "feat: improve HuggingFace model text with pipeline_tag and library metadata"
```

---

### Task 5: Clean existing bad data from production DB

**Files:** None (SQL on production)

**Step 1: SSH into production and count affected rows**

```bash
ssh root@89.167.115.45 "docker exec -i postgres-qwg00wcsoksgg84c0ww0ck8s-221857646968 psql -U postgres -d ainews -c \"
SELECT COUNT(*) as total,
       COUNT(*) FILTER (WHERE url LIKE 'https://huggingface.co/%/%') as hf_model_pages
FROM news_items
WHERE source = 'huggingface' AND url NOT LIKE '%arxiv%';
\""
```

Expected: Shows count of HF model page URLs to delete.

**Step 2: Preview items to delete**

```bash
ssh root@89.167.115.45 "docker exec -i postgres-qwg00wcsoksgg84c0ww0ck8s-221857646968 psql -U postgres -d ainews -c \"
SELECT id, title, url FROM news_items
WHERE source = 'huggingface' AND url LIKE 'https://huggingface.co/%' AND url NOT LIKE '%arxiv%'
ORDER BY created_at DESC LIMIT 20;
\""
```

Verify these are all model pages, not legitimate news.

**Step 3: Delete embeddings first (FK constraint)**

```bash
ssh root@89.167.115.45 "docker exec -i postgres-qwg00wcsoksgg84c0ww0ck8s-221857646968 psql -U postgres -d ainews -c \"
DELETE FROM item_embeddings WHERE item_id IN (
  SELECT id FROM news_items
  WHERE source = 'huggingface'
    AND url LIKE 'https://huggingface.co/%'
    AND url NOT LIKE '%arxiv%'
);
\""
```

**Step 4: Delete the bad news items**

```bash
ssh root@89.167.115.45 "docker exec -i postgres-qwg00wcsoksgg84c0ww0ck8s-221857646968 psql -U postgres -d ainews -c \"
DELETE FROM news_items
WHERE source = 'huggingface'
  AND url LIKE 'https://huggingface.co/%'
  AND url NOT LIKE '%arxiv%';
\""
```

**Step 5: Verify cleanup**

```bash
ssh root@89.167.115.45 "docker exec -i postgres-qwg00wcsoksgg84c0ww0ck8s-221857646968 psql -U postgres -d ainews -c \"
SELECT COUNT(*) FROM news_items WHERE source = 'huggingface';
\""
```

Should show only arxiv daily paper items remaining for huggingface source.

---

### Task 6: Run full test suite and deploy

**Step 1: Run full quality gate**

```bash
ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30
```
Expected: All pass

**Step 2: Deploy to production**

Push to main and let Coolify auto-deploy, or manually rebuild the pipeline-cron container:

```bash
git push origin main
```

**Step 3: Verify in production**

Wait for next cron cycle (~15 min) and check logs:

```bash
ssh root@89.167.115.45 "docker logs --since 20m pipeline-cron-qwg00wcsoksgg84c0ww0ck8s-221857646968 2>&1 | tail -30"
```

Verify:
- GitHub extractor now returns >0 items
- HuggingFace extractor filters quantized models (count should be lower than 50)
- No errors
