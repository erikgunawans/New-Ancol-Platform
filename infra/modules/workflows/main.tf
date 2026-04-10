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
# Cloud Workflows — Agent pipeline orchestrator
# ============================================================

resource "google_service_account" "workflow" {
  account_id   = "${var.prefix}-workflow"
  display_name = "MoM Compliance Workflow Orchestrator"
  project      = var.project_id
}

# Workflow SA needs to invoke Cloud Run services
resource "google_project_iam_member" "workflow_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

# Workflow SA needs Pub/Sub access (to wait for HITL decisions)
resource "google_project_iam_member" "workflow_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

# Workflow SA needs to log
resource "google_project_iam_member" "workflow_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

resource "google_workflows_workflow" "mom_compliance" {
  name            = "${var.prefix}-mom-compliance-pipeline"
  project         = var.project_id
  region          = var.region
  description     = "Orchestrates the 4-agent MoM compliance audit pipeline with HITL gates"
  service_account = google_service_account.workflow.id

  source_contents = file("${path.module}/workflow.yaml")
}
