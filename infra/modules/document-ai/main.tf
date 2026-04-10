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
# Document AI — OCR + Form Parser processor
# ============================================================

resource "google_document_ai_processor" "form_parser" {
  location     = var.region
  project      = var.project_id
  display_name = "${var.prefix}-mom-parser"
  type         = "FORM_PARSER_PROCESSOR"
}

# Eventarc trigger: Cloud Storage OBJECT_FINALIZE -> document-processor Cloud Run
resource "google_eventarc_trigger" "document_upload" {
  name     = "${var.prefix}-doc-upload-trigger"
  project  = var.project_id
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.raw_bucket_name
  }

  destination {
    cloud_run_service {
      service = var.document_processor_service_name
      region  = var.region
      path    = "/process"
    }
  }

  service_account = var.trigger_service_account_email
}
