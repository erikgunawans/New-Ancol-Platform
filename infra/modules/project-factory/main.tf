terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_project" "main" {
  name            = var.project_name
  project_id      = var.project_id
  org_id          = var.org_id
  billing_account = var.billing_account_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    system      = "ancol-mom-compliance"
  }
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "documentai.googleapis.com",
    "discoveryengine.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "workflows.googleapis.com",
    "eventarc.googleapis.com",
    "cloudtasks.googleapis.com",
    "iap.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  project = google_project.main.project_id
  service = each.key

  disable_dependent_services = false
  disable_on_destroy         = false
}
