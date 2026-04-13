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

  common_env_vars = [
    { name = "GCP_PROJECT", value = var.project_id },
    { name = "GCP_REGION", value = var.region },
    { name = "ENVIRONMENT", value = "dev" },
    { name = "DB_HOST", value = module.database.private_ip_address },
    { name = "DB_NAME", value = module.database.database_name },
    { name = "DB_USER", value = "ancol" },
    { name = "BUCKET_RAW", value = module.storage.raw_bucket_name },
    { name = "BUCKET_PROCESSED", value = module.storage.processed_bucket_name },
    { name = "BUCKET_REPORTS", value = module.storage.reports_bucket_name },
  ]

  common_secret_vars = [
    { name = "DB_PASSWORD", secret_id = module.security.db_password_secret_id },
  ]
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

  push_endpoints = {
    "extraction-agent" = "${module.run_extraction_agent.service_url}/process"
    "api-gateway"      = "${module.run_api_gateway.service_url}/api/internal/events"
  }
  push_service_account_email = module.security.service_account_emails["api-gateway"]

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
module "workflows" {
  source = "../../modules/workflows"

  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix

  depends_on = [
    module.run_extraction_agent,
    module.run_legal_research_agent,
    module.run_comparison_agent,
    module.run_reporting_agent,
    module.run_api_gateway,
  ]
}

# ── Cloud Run Services ──

module "run_api_gateway" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-api-gateway"
  service_account_email = module.security.service_account_emails["api-gateway"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  allow_unauthenticated = true
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_document_processor" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-document-processor"
  service_account_email = module.security.service_account_emails["document-processor"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  cpu                   = "2"
  memory                = "2Gi"
  request_timeout       = "600s"
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking]
}

module "run_extraction_agent" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-extraction-agent"
  service_account_email = module.security.service_account_emails["extraction-agent"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_legal_research_agent" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-legal-research-agent"
  service_account_email = module.security.service_account_emails["legal-research-agent"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  cpu                   = "2"
  memory                = "2Gi"
  request_timeout       = "600s"
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_comparison_agent" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-comparison-agent"
  service_account_email = module.security.service_account_emails["comparison-agent"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  cpu                   = "2"
  memory                = "2Gi"
  request_timeout       = "600s"
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_reporting_agent" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-reporting-agent"
  service_account_email = module.security.service_account_emails["reporting-agent"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_batch_engine" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-batch-engine"
  service_account_email = module.security.service_account_emails["batch-engine"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  min_instances         = 1
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_email_ingest" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-email-ingest"
  service_account_email = module.security.service_account_emails["email-ingest"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars = concat(local.common_env_vars, [
    { name = "EMAIL_INGEST_ADDRESS", value = "corpsec@ancol.com" },
  ])
  secret_env_vars = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_regulation_monitor" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-regulation-monitor"
  service_account_email = module.security.service_account_emails["regulation-monitor"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars              = local.common_env_vars
  secret_env_vars       = local.common_secret_vars

  depends_on = [module.security, module.networking, module.database]
}

module "run_web_frontend" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-web-frontend"
  service_account_email = module.security.service_account_emails["web-frontend"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  port                  = 3000
  allow_unauthenticated = true
  env_vars = [
    { name = "NEXT_PUBLIC_API_URL", value = module.run_api_gateway.service_url },
  ]

  depends_on = [module.security, module.networking, module.run_api_gateway]
}

# ── Module 12: Cloud Scheduler ──
module "scheduler" {
  source = "../../modules/scheduler"

  project_id                    = var.project_id
  region                        = var.region
  prefix                        = local.prefix
  email_ingest_url              = module.run_email_ingest.service_url
  regulation_monitor_url        = module.run_regulation_monitor.service_url
  invoker_service_account_email = module.security.service_account_emails["api-gateway"]

  depends_on = [module.run_email_ingest, module.run_regulation_monitor]
}

# ── Module 13: Disaster Recovery ──
module "disaster_recovery" {
  source = "../../modules/disaster-recovery"

  project_id               = var.project_id
  prefix                   = local.prefix
  environment              = local.environment
  primary_db_instance_name = module.database.instance_name
  vpc_network_id           = module.networking.network_id
  kms_key_id               = module.security.kms_key_id
  bucket_raw               = module.storage.raw_bucket_name
  bucket_reports           = module.storage.reports_bucket_name
  notification_channels    = [module.monitoring.notification_channel_id]

  depends_on = [module.database, module.storage, module.monitoring]
}

# ── Module 14: Spanner Graph (Regulation Knowledge Graph) ──
module "spanner_graph" {
  source = "../../modules/spanner-graph"

  project_id  = var.project_id
  region      = var.region
  prefix      = local.prefix
  environment = local.environment

  depends_on = [module.project]
}

# ── Cloud Run: Gemini Agent Webhook ──
module "run_gemini_agent" {
  source = "../../modules/cloud-run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${local.prefix}-gemini-agent"
  service_account_email = module.security.service_account_emails["gemini-agent"]
  vpc_connector_id      = module.networking.vpc_connector_id
  environment           = local.environment
  push_invoker_sa       = module.security.service_account_emails["api-gateway"]
  env_vars = concat(local.common_env_vars, [
    { name = "API_GATEWAY_URL", value = module.run_api_gateway.service_url },
    { name = "GRAPH_BACKEND", value = "spanner" },
    { name = "SPANNER_INSTANCE", value = module.spanner_graph.instance_name },
    { name = "SPANNER_DATABASE", value = module.spanner_graph.database_name },
  ])
  secret_env_vars = local.common_secret_vars

  depends_on = [
    module.security,
    module.networking,
    module.run_api_gateway,
    module.spanner_graph,
  ]
}
