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
# Vertex AI Search — Regulatory corpus datastore + search app
# ============================================================

resource "google_discovery_engine_data_store" "regulatory_corpus" {
  location                    = var.region
  project                     = var.project_id
  data_store_id               = "${var.prefix}-regulatory-corpus"
  display_name                = "Regulatory Corpus"
  industry_vertical           = "GENERIC"
  content_config              = "CONTENT_REQUIRED"
  solution_types              = ["SOLUTION_TYPE_SEARCH"]
  create_advanced_site_search = false

  document_processing_config {
    default_parsing_config {
      digital_parsing_config {}
    }
  }
}

resource "google_discovery_engine_search_engine" "regulatory_search" {
  engine_id      = "${var.prefix}-regulatory-search"
  collection_id  = "default_collection"
  location       = var.region
  project        = var.project_id
  display_name   = "Regulatory Search Engine"
  industry_vertical = "GENERIC"

  data_store_ids = [
    google_discovery_engine_data_store.regulatory_corpus.data_store_id
  ]

  search_engine_config {
    search_tier    = "SEARCH_TIER_ENTERPRISE"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }
}

# ============================================================
# Vertex AI Search — Contract clauses datastore + search app
# ============================================================

resource "google_discovery_engine_data_store" "contract_clauses" {
  location                    = var.region
  project                     = var.project_id
  data_store_id               = "${var.prefix}-contract-clauses"
  display_name                = "Contract Clauses"
  industry_vertical           = "GENERIC"
  content_config              = "CONTENT_REQUIRED"
  solution_types              = ["SOLUTION_TYPE_SEARCH"]
  create_advanced_site_search = false

  document_processing_config {
    default_parsing_config {
      digital_parsing_config {}
    }
  }
}

resource "google_discovery_engine_search_engine" "contract_search" {
  engine_id         = "${var.prefix}-contract-search"
  collection_id     = "default_collection"
  location          = var.region
  project           = var.project_id
  display_name      = "Contract Search Engine"
  industry_vertical = "GENERIC"

  data_store_ids = [
    google_discovery_engine_data_store.contract_clauses.data_store_id
  ]

  search_engine_config {
    search_tier    = "SEARCH_TIER_ENTERPRISE"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }
}
