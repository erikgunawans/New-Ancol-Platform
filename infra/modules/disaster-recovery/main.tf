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
# Disaster Recovery — RPO 1hr / RTO 4hr
# ============================================================

# Cross-region Cloud SQL read replica for failover
resource "google_sql_database_instance" "replica" {
  name                 = "${var.prefix}-db-replica"
  project              = var.project_id
  region               = var.dr_region
  database_version     = "POSTGRES_15"
  master_instance_name = var.primary_db_instance_name

  replica_configuration {
    failover_target = true
  }

  settings {
    tier              = var.db_tier
    availability_type = "REGIONAL"
    disk_size         = var.db_disk_size_gb

    backup_configuration {
      enabled = false # Replica doesn't need separate backup
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.vpc_network_id
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }
  }

  deletion_protection = true
}

# GCS bucket replication — raw documents
resource "google_storage_bucket" "raw_dr" {
  name          = "${var.prefix}-mom-raw-dr"
  project       = var.project_id
  location      = var.dr_region
  storage_class = "NEARLINE"
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 3650 # 10 years
    }
  }

  encryption {
    default_kms_key_name = var.kms_key_id
  }

  labels = {
    environment = var.environment
    purpose     = "disaster-recovery"
  }
}

# GCS bucket replication — reports
resource "google_storage_bucket" "reports_dr" {
  name          = "${var.prefix}-mom-reports-dr"
  project       = var.project_id
  location      = var.dr_region
  storage_class = "NEARLINE"
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 3650
    }
  }

  encryption {
    default_kms_key_name = var.kms_key_id
  }

  labels = {
    environment = var.environment
    purpose     = "disaster-recovery"
  }
}

# Cloud Storage Transfer — replicate raw bucket to DR region (every 1 hour)
resource "google_storage_transfer_job" "raw_replication" {
  description = "Replicate raw MoM documents to DR region"
  project     = var.project_id

  transfer_spec {
    gcs_data_source {
      bucket_name = var.bucket_raw
    }
    gcs_data_sink {
      bucket_name = google_storage_bucket.raw_dr.name
    }
  }

  schedule {
    schedule_start_date {
      year  = 2026
      month = 4
      day   = 10
    }
    start_time_of_day {
      hours   = 0
      minutes = 0
      seconds = 0
      nanos   = 0
    }
    repeat_interval = "3600s" # Every hour — RPO 1hr
  }
}

# Cloud Storage Transfer — replicate reports bucket
resource "google_storage_transfer_job" "reports_replication" {
  description = "Replicate compliance reports to DR region"
  project     = var.project_id

  transfer_spec {
    gcs_data_source {
      bucket_name = var.bucket_reports
    }
    gcs_data_sink {
      bucket_name = google_storage_bucket.reports_dr.name
    }
  }

  schedule {
    schedule_start_date {
      year  = 2026
      month = 4
      day   = 10
    }
    start_time_of_day {
      hours   = 0
      minutes = 0
      seconds = 0
      nanos   = 0
    }
    repeat_interval = "3600s"
  }
}

# Cloud SQL automated backup — every 1 hour
# (This is configured on the primary instance, not the replica)
# The primary database module should have backup_configuration with
# point_in_time_recovery_enabled = true and transaction_log_retention_days = 7

# DR health monitoring — alert if replica lag exceeds 5 minutes
resource "google_monitoring_alert_policy" "replica_lag" {
  display_name = "DB Replica Lag > 5 minutes"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL replica lag"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.project_id}:${google_sql_database_instance.replica.name}\" AND metric.type = \"cloudsql.googleapis.com/database/replication/replica_lag\""
      comparison      = "COMPARISON_GT"
      threshold_value = 300 # 5 minutes in seconds
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = var.notification_channels

  documentation {
    content = "Database replica lag exceeds 5 minutes. RPO target is 1 hour. Investigate replication health."
  }
}
