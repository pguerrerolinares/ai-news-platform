"""Prometheus metrics for observability."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

# Application info
app_info = Info("ainews", "AI News Platform information")
app_info.info({"version": "0.1.0"})

# Pipeline metrics
pipeline_runs_total = Counter(
    "ainews_pipeline_runs_total",
    "Total pipeline executions",
    ["status"],
)
pipeline_duration_seconds = Histogram(
    "ainews_pipeline_duration_seconds",
    "Pipeline execution duration",
    buckets=[30, 60, 120, 300, 600],
)
items_extracted_total = Counter(
    "ainews_items_extracted_total",
    "Total items extracted",
    ["source"],
)
items_stored_total = Counter(
    "ainews_items_stored_total",
    "Total items stored in database",
)

# API metrics
api_requests_total = Counter(
    "ainews_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
api_request_duration_seconds = Histogram(
    "ainews_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
)

# Extractor metrics
extractor_duration_seconds = Histogram(
    "ainews_extractor_duration_seconds",
    "Extractor execution duration",
    ["source"],
    buckets=[5, 10, 30, 60, 120],
)
extractor_errors_total = Counter(
    "ainews_extractor_errors_total",
    "Total extractor errors",
    ["source"],
)

# Classification metrics
classification_duration_seconds = Histogram(
    "ainews_classification_duration_seconds",
    "Classification execution duration",
    buckets=[5, 10, 30, 60, 120],
)
items_classified_total = Counter(
    "ainews_items_classified_total",
    "Total items classified",
)

# Validation metrics
validation_duration_seconds = Histogram(
    "ainews_validation_duration_seconds",
    "Validation execution duration",
    buckets=[5, 10, 30, 60, 120],
)
items_validated_total = Counter(
    "ainews_items_validated_total",
    "Total items validated",
)
items_filtered_total = Counter(
    "ainews_items_filtered_total",
    "Total items filtered",
    ["reason"],
)

# Pipeline validation metrics (M14)
items_validation_failed_total = Counter(
    "ainews_items_validation_failed_total",
    "Items rejected by pre-storage validation",
    ["reason"],
)

# Embedding metrics (M14)
embedding_failures_total = Counter(
    "ainews_embedding_failures_total",
    "Total embedding generation failures",
)
