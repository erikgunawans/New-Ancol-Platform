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
# Cloud Monitoring — Alert policies
# ============================================================

# Notification channel (email)
resource "google_monitoring_notification_channel" "email" {
  display_name = "Compliance Team Email"
  project      = var.project_id
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

# Alert: Cloud Run service error rate > 5%
resource "google_monitoring_alert_policy" "agent_error_rate" {
  display_name = "Agent Error Rate > 5%"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx error rate"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  alert_strategy {
    auto_close = "1800s"
  }
}

# Alert: Cloud SQL CPU > 80%
resource "google_monitoring_alert_policy" "db_cpu" {
  display_name = "Database CPU > 80%"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL CPU utilization"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}

# Alert: Pub/Sub DLQ message count > 0 (failed messages)
resource "google_monitoring_alert_policy" "dlq_messages" {
  display_name = "Dead Letter Queue Has Messages"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "DLQ message count"

    condition_threshold {
      filter          = "resource.type = \"pubsub_subscription\" AND resource.labels.subscription_id = monitoring.regex.full_match(\".*-dlq-.*\") AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}

# ============================================================
# Phase 4 — Batch, HITL SLA, corpus staleness, Gemini quota
# ============================================================

resource "google_monitoring_alert_policy" "hitl_sla_breach" {
  display_name = "HITL Review SLA Breach (>48h)"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "HITL items waiting beyond SLA"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ancol-api-gateway\" AND metric.type = \"logging.googleapis.com/user/hitl_sla_breach_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  documentation {
    content = "One or more HITL review items have exceeded the 48-hour SLA."
  }
}

resource "google_monitoring_alert_policy" "batch_failure_rate" {
  display_name = "Batch Processing Failure Rate > 10%"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Batch engine error rate"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ancol-batch-engine\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 10
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  documentation {
    content = "Batch engine is experiencing >10% failure rate."
  }
}

resource "google_monitoring_alert_policy" "corpus_staleness" {
  display_name = "Regulatory Corpus Stale (>30 days)"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Corpus last updated >30 days ago"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"logging.googleapis.com/user/corpus_staleness_days\""
      comparison      = "COMPARISON_GT"
      threshold_value = 30
      duration        = "86400s"

      aggregations {
        alignment_period   = "86400s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  documentation {
    content = "Regulatory corpus not updated in >30 days. Check for new/amended regulations."
  }
}

resource "google_monitoring_alert_policy" "gemini_quota" {
  display_name = "Gemini API Quota > 80%"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Gemini API quota usage"

    condition_threshold {
      filter          = "resource.type = \"consumer_quota\" AND resource.labels.service = \"generativelanguage.googleapis.com\" AND metric.type = \"serviceruntime.googleapis.com/quota/rate/net_usage\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  documentation {
    content = "Gemini API quota above 80%. Consider reducing batch concurrency or requesting quota increase."
  }
}
