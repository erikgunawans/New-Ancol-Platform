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
# Cloud KMS — Encryption at rest
# ============================================================

resource "google_kms_key_ring" "main" {
  name     = "${var.prefix}-keyring"
  project  = var.project_id
  location = var.region
}

resource "google_kms_crypto_key" "data_key" {
  name            = "${var.prefix}-data-key"
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s" # 90 days
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ============================================================
# Service Accounts — One per agent/service (least privilege)
# ============================================================

locals {
  service_accounts = {
    "api-gateway"          = "API Gateway service"
    "extraction-agent"     = "Extraction Agent (Gemini Flash)"
    "legal-research-agent" = "Legal Research Agent (Gemini Pro + RAG)"
    "comparison-agent"     = "Comparison & Reasoning Agent (Gemini Pro)"
    "reporting-agent"      = "Reporting Agent (Gemini Flash)"
    "document-processor"   = "Document AI processor service"
    "web-frontend"         = "Next.js frontend service"
    "batch-engine"         = "Batch processing orchestrator"
    "email-ingest"         = "Gmail inbox scanner"
    "regulation-monitor"   = "Regulation change detector"
    "gemini-agent"         = "Gemini Agent Builder webhook service"
  }
}

resource "google_service_account" "agents" {
  for_each = local.service_accounts

  account_id   = "${var.prefix}-${each.key}"
  display_name = each.value
  project      = var.project_id
}

# ============================================================
# IAM Bindings — Per-service roles
# ============================================================

# All agents: Vertex AI user (Gemini API access)
resource "google_project_iam_member" "agent_vertex_ai" {
  for_each = toset([
    "extraction-agent",
    "legal-research-agent",
    "comparison-agent",
    "reporting-agent",
  ])

  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# All agents: Pub/Sub publisher
resource "google_project_iam_member" "agent_pubsub_publisher" {
  for_each = toset([
    "api-gateway",
    "extraction-agent",
    "legal-research-agent",
    "comparison-agent",
    "reporting-agent",
    "document-processor",
    "batch-engine",
    "email-ingest",
    "regulation-monitor",
    "gemini-agent",
  ])

  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# All agents: Cloud SQL client
resource "google_project_iam_member" "agent_sql_client" {
  for_each = toset([
    "api-gateway",
    "extraction-agent",
    "legal-research-agent",
    "comparison-agent",
    "reporting-agent",
    "batch-engine",
    "email-ingest",
    "gemini-agent",
  ])

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# Document processor: Document AI API user
resource "google_project_iam_member" "docai_user" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.agents["document-processor"].email}"
}

# Document processor: Storage object admin (read raw, write processed)
resource "google_project_iam_member" "docproc_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.agents["document-processor"].email}"
}

# Legal Research Agent: Discovery Engine viewer (Vertex AI Search)
resource "google_project_iam_member" "legal_discovery" {
  project = var.project_id
  role    = "roles/discoveryengine.viewer"
  member  = "serviceAccount:${google_service_account.agents["legal-research-agent"].email}"
}

# Reporting Agent: Storage writer (upload PDF/Excel reports)
resource "google_project_iam_member" "reporting_storage" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.agents["reporting-agent"].email}"
}

# API Gateway: Storage reader (serve reports for download)
resource "google_project_iam_member" "api_storage_reader" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.agents["api-gateway"].email}"
}

# API Gateway: Storage creator for contracts bucket (upload)
# Note: objectViewer already granted above for report downloads — covers read access.
# Using objectCreator (not objectAdmin) to avoid granting delete on all buckets.
# Bucket-level IAM should be added when dev/main.tf wires the storage module output.
resource "google_project_iam_member" "api_contracts_storage" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.agents["api-gateway"].email}"
}

# Extraction Agent: Storage viewer for contracts bucket (read for extraction)
resource "google_project_iam_member" "extraction_contracts_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.agents["extraction-agent"].email}"
}

# API Gateway: BigQuery data editor (audit trail writes)
resource "google_project_iam_member" "api_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.agents["api-gateway"].email}"
}

# ============================================================
# Secret Manager — Sensitive configuration
# ============================================================

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.prefix}-db-password"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret" "sendgrid_api_key" {
  secret_id = "${var.prefix}-sendgrid-api-key"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret" "whatsapp_api_token" {
  secret_id = "${var.prefix}-whatsapp-api-token"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

# Allow API Gateway to access secrets
resource "google_secret_manager_secret_iam_member" "api_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agents["api-gateway"].email}"
}

resource "google_secret_manager_secret_iam_member" "api_sendgrid" {
  secret_id = google_secret_manager_secret.sendgrid_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agents["api-gateway"].email}"
}

# Allow all agents to access DB password
resource "google_secret_manager_secret_iam_member" "agent_db_password" {
  for_each = toset([
    "extraction-agent",
    "legal-research-agent",
    "comparison-agent",
    "reporting-agent",
    "batch-engine",
    "email-ingest",
    "gemini-agent",
  ])

  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# Batch Engine: Storage viewer (read documents for processing)
resource "google_project_iam_member" "batch_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.agents["batch-engine"].email}"
}

# Email Ingest: Storage admin (upload attachments to raw bucket)
resource "google_project_iam_member" "email_ingest_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.agents["email-ingest"].email}"
}

# Regulation Monitor: Discovery Engine editor (update Vertex AI Search corpus)
resource "google_project_iam_member" "regulation_discovery" {
  project = var.project_id
  role    = "roles/discoveryengine.editor"
  member  = "serviceAccount:${google_service_account.agents["regulation-monitor"].email}"
}

# Gemini Agent: Spanner database user
resource "google_project_iam_member" "gemini_agent_spanner" {
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.agents["gemini-agent"].email}"
}

# ============================================================
# Cloud Armor — WAF + DDoS protection
# ============================================================

resource "google_compute_security_policy" "main" {
  name    = "${var.prefix}-security-policy"
  project = var.project_id

  # Default rule: allow
  rule {
    action   = "allow"
    priority = 2147483647

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    description = "Default allow rule"
  }

  # Rate limiting rule
  rule {
    action   = "rate_based_ban"
    priority = 1000

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"

      rate_limit_threshold {
        count        = 100
        interval_sec = 60
      }

      ban_duration_sec = 300
    }

    description = "Rate limit: 100 requests/minute per IP"
  }
}
