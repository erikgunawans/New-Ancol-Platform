terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ============================================================
# BigQuery — Analytics dataset + audit log sink
# ============================================================

resource "google_bigquery_dataset" "compliance" {
  dataset_id  = "${replace(var.prefix, "-", "_")}_compliance"
  project     = var.project_id
  location    = var.region
  description = "Compliance analytics and immutable audit trail"

  default_table_expiration_ms = null # No auto-expiry (10+ year retention)

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }

  access {
    role          = "WRITER"
    user_by_email = var.audit_writer_sa_email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

# Audit events table (append-only, immutable)
resource "google_bigquery_table" "audit_events" {
  dataset_id          = google_bigquery_dataset.compliance.dataset_id
  table_id            = "audit_events"
  project             = var.project_id
  deletion_protection = true
  description         = "Immutable audit trail — every action by users, agents, and system"

  time_partitioning {
    type  = "MONTH"
    field = "timestamp"
  }

  clustering = ["actor_type", "action", "resource_type"]

  schema = jsonencode([
    { name = "id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "actor_type", type = "STRING", mode = "REQUIRED" },
    { name = "actor_id", type = "STRING", mode = "REQUIRED" },
    { name = "actor_role", type = "STRING", mode = "NULLABLE" },
    { name = "action", type = "STRING", mode = "REQUIRED" },
    { name = "resource_type", type = "STRING", mode = "REQUIRED" },
    { name = "resource_id", type = "STRING", mode = "REQUIRED" },
    { name = "details", type = "JSON", mode = "NULLABLE" },
    { name = "ip_address", type = "STRING", mode = "NULLABLE" },
    { name = "user_agent", type = "STRING", mode = "NULLABLE" },
    { name = "model_used", type = "STRING", mode = "NULLABLE" },
    { name = "prompt_tokens", type = "INTEGER", mode = "NULLABLE" },
    { name = "completion_tokens", type = "INTEGER", mode = "NULLABLE" },
    { name = "processing_time_ms", type = "INTEGER", mode = "NULLABLE" },
  ])
}

# Compliance scores table (for trend analytics)
resource "google_bigquery_table" "compliance_scores" {
  dataset_id          = google_bigquery_dataset.compliance.dataset_id
  table_id            = "compliance_scores"
  project             = var.project_id
  deletion_protection = false
  description         = "Historical compliance scores for trend analysis"

  time_partitioning {
    type  = "MONTH"
    field = "meeting_date"
  }

  schema = jsonencode([
    { name = "document_id", type = "STRING", mode = "REQUIRED" },
    { name = "meeting_date", type = "DATE", mode = "REQUIRED" },
    { name = "structural_score", type = "FLOAT", mode = "REQUIRED" },
    { name = "substantive_score", type = "FLOAT", mode = "REQUIRED" },
    { name = "regulatory_score", type = "FLOAT", mode = "REQUIRED" },
    { name = "composite_score", type = "FLOAT", mode = "REQUIRED" },
    { name = "critical_findings", type = "INTEGER", mode = "REQUIRED" },
    { name = "high_findings", type = "INTEGER", mode = "REQUIRED" },
    { name = "medium_findings", type = "INTEGER", mode = "REQUIRED" },
    { name = "low_findings", type = "INTEGER", mode = "REQUIRED" },
    { name = "red_flag_count", type = "INTEGER", mode = "REQUIRED" },
    { name = "processed_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# Cloud Audit Logs sink to BigQuery
resource "google_logging_project_sink" "audit_to_bq" {
  name    = "${var.prefix}-audit-to-bq"
  project = var.project_id

  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.compliance.dataset_id}"

  filter = "resource.type=\"cloud_run_revision\" OR resource.type=\"cloud_sql_database\""

  unique_writer_identity = true

  bigquery_options {
    use_partitioned_tables = true
  }
}

# Grant the log sink writer access to BigQuery
resource "google_bigquery_dataset_iam_member" "log_sink_writer" {
  dataset_id = google_bigquery_dataset.compliance.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.audit_to_bq.writer_identity
}

# ============================================================
# Analytics Views — materialized from compliance_scores table
# ============================================================

# Monthly compliance trend view
resource "google_bigquery_table" "view_monthly_trends" {
  dataset_id          = google_bigquery_dataset.compliance.dataset_id
  table_id            = "v_monthly_compliance_trends"
  project             = var.project_id
  deletion_protection = false
  description         = "Monthly aggregated compliance scores for trend dashboards"

  view {
    query          = <<-SQL
      SELECT
        FORMAT_DATE('%Y-%m', meeting_date) AS period,
        COUNT(*) AS document_count,
        ROUND(AVG(structural_score), 1) AS avg_structural,
        ROUND(AVG(substantive_score), 1) AS avg_substantive,
        ROUND(AVG(regulatory_score), 1) AS avg_regulatory,
        ROUND(AVG(composite_score), 1) AS avg_composite,
        SUM(critical_findings) AS total_critical,
        SUM(high_findings) AS total_high,
        SUM(red_flag_count) AS total_red_flags
      FROM `${var.project_id}.${google_bigquery_dataset.compliance.dataset_id}.compliance_scores`
      GROUP BY period
      ORDER BY period DESC
    SQL
    use_legacy_sql = false
  }
}

# Violation type heatmap view
resource "google_bigquery_table" "view_violation_heatmap" {
  dataset_id          = google_bigquery_dataset.compliance.dataset_id
  table_id            = "v_violation_heatmap"
  project             = var.project_id
  deletion_protection = false
  description         = "Red flag type distribution across processed documents"

  view {
    query          = <<-SQL
      SELECT
        FORMAT_DATE('%Y-%m', meeting_date) AS period,
        SUM(critical_findings) AS critical,
        SUM(high_findings) AS high,
        SUM(medium_findings) AS medium,
        SUM(low_findings) AS low,
        SUM(red_flag_count) AS red_flags,
        COUNT(*) AS documents
      FROM `${var.project_id}.${google_bigquery_dataset.compliance.dataset_id}.compliance_scores`
      GROUP BY period
      ORDER BY period DESC
    SQL
    use_legacy_sql = false
  }
}

# Coverage by year and type view
resource "google_bigquery_table" "view_coverage" {
  dataset_id          = google_bigquery_dataset.compliance.dataset_id
  table_id            = "v_coverage_by_year"
  project             = var.project_id
  deletion_protection = false
  description         = "Document processing coverage by year"

  view {
    query          = <<-SQL
      SELECT
        EXTRACT(YEAR FROM meeting_date) AS year,
        COUNT(*) AS total_processed,
        ROUND(AVG(composite_score), 1) AS avg_score,
        SUM(CASE WHEN composite_score >= 80 THEN 1 ELSE 0 END) AS compliant_count,
        SUM(CASE WHEN composite_score < 60 THEN 1 ELSE 0 END) AS non_compliant_count
      FROM `${var.project_id}.${google_bigquery_dataset.compliance.dataset_id}.compliance_scores`
      GROUP BY year
      ORDER BY year DESC
    SQL
    use_legacy_sql = false
  }
}
