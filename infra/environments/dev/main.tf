terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "ancol-terraform-state"
    prefix = "dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  prefix      = "ancol"
  environment = "dev"
}

# ── Module 1: Project Factory ──
module "project" {
  source = "../../modules/project-factory"

  project_id         = var.project_id
  project_name       = "Ancol MoM Compliance (Dev)"
  billing_account_id = var.billing_account_id
  environment        = local.environment
}

# ── Module 2: Networking ──
module "networking" {
  source = "../../modules/networking"

  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix

  depends_on = [module.project]
}

# ── Module 3: Security ──
module "security" {
  source = "../../modules/security"

  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix

  depends_on = [module.project]
}

# ── Module 4: Storage ──
module "storage" {
  source = "../../modules/storage"

  project_id  = var.project_id
  region      = var.region
  kms_key_id  = module.security.kms_key_id
  environment = local.environment

  depends_on = [module.security]
}

# ── Module 5: Database ──
module "database" {
  source = "../../modules/database"

  project_id             = var.project_id
  region                 = var.region
  prefix                 = local.prefix
  network_id             = module.networking.network_id
  private_vpc_connection = module.networking.private_vpc_connection
  database_password      = var.database_password
  environment            = local.environment

  # Dev settings
  tier              = "db-f1-micro"
  availability_type = "ZONAL"
  disk_size_gb      = 20

  depends_on = [module.networking]
}

# ── Module 6: Pub/Sub ──
module "pubsub" {
  source = "../../modules/pubsub"

  project_id  = var.project_id
  prefix      = local.prefix
  environment = local.environment

  # Push endpoints set to empty in dev (configured after Cloud Run deploys)
  push_endpoints             = {}
  push_service_account_email = ""

  depends_on = [module.project]
}

# ── Module 7: Vertex AI Search ──
module "vertex_ai_search" {
  source = "../../modules/vertex-ai-search"

  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix

  depends_on = [module.project]
}

# ── Module 8: BigQuery ──
module "bigquery" {
  source = "../../modules/bigquery"

  project_id            = var.project_id
  region                = var.region
  prefix                = local.prefix
  environment           = local.environment
  audit_writer_sa_email = module.security.service_account_emails["api-gateway"]

  depends_on = [module.security]
}

# ── Module 9: Monitoring ──
module "monitoring" {
  source = "../../modules/monitoring"

  project_id  = var.project_id
  alert_email = var.alert_email

  depends_on = [module.project]
}

# ── Module 10: Auth (IAP) ──
# Commented out for initial dev — enable when Cloud Identity is configured
# module "auth" {
#   source = "../../modules/auth"
#
#   project_id         = var.project_id
#   project_number     = module.project.project_number
#   support_email      = var.support_email
#   authorized_members = var.authorized_members
# }

# ── Module 11: Workflows ──
# Deployed after agents are running (Phase 2, Week 8)
# module "workflows" {
#   source = "../../modules/workflows"
#
#   project_id = var.project_id
#   region     = var.region
#   prefix     = local.prefix
# }
