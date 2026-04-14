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
# Cloud Scheduler — Automated triggers for email & regulation scanning
# ============================================================

# Email inbox scan — every 15 minutes
resource "google_cloud_scheduler_job" "email_scan" {
  name        = "${var.prefix}-email-scan"
  project     = var.project_id
  region      = var.region
  description = "Scan Corporate Secretary Gmail inbox for new MoM attachments"
  schedule    = "*/15 * * * *"
  time_zone   = "Asia/Jakarta"

  http_target {
    uri         = "${var.email_ingest_url}/scan"
    http_method = "POST"

    oidc_token {
      service_account_email = var.invoker_service_account_email
    }
  }

  retry_config {
    retry_count          = 1
    min_backoff_duration = "5s"
    max_backoff_duration = "5s"
  }
}

# Regulation check — daily at 06:00 WIB
resource "google_cloud_scheduler_job" "regulation_check" {
  name        = "${var.prefix}-regulation-check"
  project     = var.project_id
  region      = var.region
  description = "Check OJK/IDX/industry sources for new regulation changes"
  schedule    = "0 6 * * *"
  time_zone   = "Asia/Jakarta"

  http_target {
    uri         = "${var.regulation_monitor_url}/check"
    http_method = "POST"

    oidc_token {
      service_account_email = var.invoker_service_account_email
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "120s"
  }
}

# Obligation deadline check — daily at 07:00 WIB
resource "google_cloud_scheduler_job" "obligation_check" {
  name        = "${var.prefix}-obligation-check"
  project     = var.project_id
  region      = var.region
  description = "Check contract obligation deadlines and send reminders (30/14/7 days)"
  schedule    = "0 7 * * *"
  time_zone   = "Asia/Jakarta"

  http_target {
    uri         = "${var.api_gateway_url}/api/obligations/check-deadlines"
    http_method = "POST"

    oidc_token {
      service_account_email = var.invoker_service_account_email
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "120s"
  }
}
