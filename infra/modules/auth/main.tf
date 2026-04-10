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
# Identity-Aware Proxy (IAP) — Zero-trust access
# ============================================================

# IAP OAuth brand (consent screen)
resource "google_iap_brand" "main" {
  support_email     = var.support_email
  application_title = "Ancol MoM Compliance System"
  project           = var.project_number
}

# IAP OAuth client
resource "google_iap_client" "main" {
  display_name = "Ancol MoM Compliance Web"
  brand        = google_iap_brand.main.name
}

# IAP access for authorized users
resource "google_iap_web_iam_member" "authorized_users" {
  for_each = toset(var.authorized_members)

  project = var.project_id
  role    = "roles/iap.httpsResourceAccessAllowed"
  member  = each.value
}
