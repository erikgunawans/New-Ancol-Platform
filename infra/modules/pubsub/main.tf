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
# Pub/Sub Topics + DLQs + Subscriptions
# 8 main topics, each with a dead-letter topic
# ============================================================

locals {
  topics = {
    "mom-uploaded" = {
      description = "Document AI processing complete, ready for extraction"
      push_target = "extraction-agent"
    }
    "mom-extracted" = {
      description = "Extraction complete, pending HITL Gate 1"
      push_target = "api-gateway"
    }
    "mom-researched" = {
      description = "Legal research complete, pending HITL Gate 2"
      push_target = "api-gateway"
    }
    "mom-compared" = {
      description = "Comparison complete, pending HITL Gate 3"
      push_target = "api-gateway"
    }
    "mom-reported" = {
      description = "Report generated, pending HITL Gate 4"
      push_target = "api-gateway"
    }
    "hitl-pending" = {
      description = "New item awaiting human review"
      push_target = "api-gateway"
    }
    "hitl-decided" = {
      description = "Human decision made, resume pipeline"
      push_target = "" # Consumed by Cloud Workflows
    }
    "batch-progress" = {
      description = "Batch processing status updates"
      push_target = "api-gateway"
    }
  }
}

# Main topics
resource "google_pubsub_topic" "main" {
  for_each = local.topics

  name    = "${var.prefix}-${each.key}"
  project = var.project_id

  message_retention_duration = "86400s" # 24 hours

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Dead-letter topics
resource "google_pubsub_topic" "dlq" {
  for_each = local.topics

  name    = "${var.prefix}-${each.key}-dlq"
  project = var.project_id

  message_retention_duration = "604800s" # 7 days for DLQ

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    is_dlq      = "true"
  }
}

# Push subscriptions (for topics with push targets)
resource "google_pubsub_subscription" "push" {
  for_each = {
    for k, v in local.topics : k => v if v.push_target != "" && contains(keys(var.push_endpoints), v.push_target)
  }

  name    = "${var.prefix}-${each.key}-push"
  project = var.project_id
  topic   = google_pubsub_topic.main[each.key].id

  ack_deadline_seconds = 600 # 10 minutes (agents may take time)

  push_config {
    push_endpoint = var.push_endpoints[each.value.push_target]

    oidc_token {
      service_account_email = var.push_service_account_email
    }

    attributes = {
      x-goog-version = "v1"
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq[each.key].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s" # 10 minutes max backoff
  }

  expiration_policy {
    ttl = "" # Never expire
  }

  labels = {
    environment = var.environment
  }
}

# Pull subscription for hitl-decided (consumed by Cloud Workflows)
resource "google_pubsub_subscription" "hitl_decided_pull" {
  name    = "${var.prefix}-hitl-decided-pull"
  project = var.project_id
  topic   = google_pubsub_topic.main["hitl-decided"].id

  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["hitl-decided"].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
    consumer    = "cloud-workflows"
  }
}

# DLQ subscriptions (pull-based for manual inspection)
resource "google_pubsub_subscription" "dlq" {
  for_each = local.topics

  name    = "${var.prefix}-${each.key}-dlq-pull"
  project = var.project_id
  topic   = google_pubsub_topic.dlq[each.key].id

  ack_deadline_seconds = 60

  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
    is_dlq      = "true"
  }
}
