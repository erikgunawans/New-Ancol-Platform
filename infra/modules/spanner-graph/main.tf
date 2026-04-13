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
# Cloud Spanner — Regulation Knowledge Graph
# ============================================================

resource "google_spanner_instance" "main" {
  name             = "${var.prefix}-regulation-graph"
  config           = "regional-${var.region}"
  display_name     = "Regulation Knowledge Graph"
  processing_units = var.processing_units
  project          = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_spanner_database" "regulations" {
  instance            = google_spanner_instance.main.name
  name                = "${var.prefix}-regulations"
  project             = var.project_id
  database_dialect    = "GOOGLE_STANDARD_SQL"
  deletion_protection = false

  ddl = [
    # -----------------------------------------------------------
    # Node tables
    # -----------------------------------------------------------
    <<-EOT
      CREATE TABLE Regulations (
        id              STRING(64) NOT NULL,
        title           STRING(1024),
        issuer          STRING(64),
        effective_date  DATE,
        status          STRING(32),
        authority_level INT64
      ) PRIMARY KEY (id)
    EOT
    ,
    <<-EOT
      CREATE TABLE Clauses (
        id              STRING(64) NOT NULL,
        regulation_id   STRING(64) NOT NULL,
        clause_number   STRING(32),
        text_summary    STRING(4096),
        domain          STRING(64)
      ) PRIMARY KEY (id)
    EOT
    ,
    <<-EOT
      CREATE TABLE Domains (
        name STRING(64) NOT NULL
      ) PRIMARY KEY (name)
    EOT
    ,

    # -----------------------------------------------------------
    # Edge tables
    # -----------------------------------------------------------
    <<-EOT
      CREATE TABLE Amends (
        source_id      STRING(64) NOT NULL,
        target_id      STRING(64) NOT NULL,
        effective_date DATE,
        change_type    STRING(32)
      ) PRIMARY KEY (source_id, target_id)
    EOT
    ,
    <<-EOT
      CREATE TABLE Supersedes (
        source_id      STRING(64) NOT NULL,
        target_id      STRING(64) NOT NULL,
        effective_date DATE
      ) PRIMARY KEY (source_id, target_id)
    EOT
    ,
    <<-EOT
      CREATE TABLE References (
        source_clause_id STRING(64) NOT NULL,
        target_clause_id STRING(64) NOT NULL,
        reference_type   STRING(32)
      ) PRIMARY KEY (source_clause_id, target_clause_id)
    EOT
    ,
    <<-EOT
      CREATE TABLE RegulationDomains (
        regulation_id STRING(64) NOT NULL,
        domain_name   STRING(64) NOT NULL,
        scope         STRING(256)
      ) PRIMARY KEY (regulation_id, domain_name)
    EOT
    ,
    <<-EOT
      CREATE TABLE ClauseDomains (
        clause_id   STRING(64) NOT NULL,
        domain_name STRING(64) NOT NULL
      ) PRIMARY KEY (clause_id, domain_name)
    EOT
    ,

    # -----------------------------------------------------------
    # Property graph
    # -----------------------------------------------------------
    <<-EOT
      CREATE PROPERTY GRAPH RegulationGraph
        NODE TABLES (
          Regulations
            KEY (id),
          Clauses
            KEY (id),
          Domains
            KEY (name)
        )
        EDGE TABLES (
          Amends
            KEY (source_id, target_id)
            SOURCE KEY (source_id) REFERENCES Regulations (id)
            DESTINATION KEY (target_id) REFERENCES Regulations (id),
          Supersedes
            KEY (source_id, target_id)
            SOURCE KEY (source_id) REFERENCES Regulations (id)
            DESTINATION KEY (target_id) REFERENCES Regulations (id),
          References
            KEY (source_clause_id, target_clause_id)
            SOURCE KEY (source_clause_id) REFERENCES Clauses (id)
            DESTINATION KEY (target_clause_id) REFERENCES Clauses (id),
          RegulationDomains
            KEY (regulation_id, domain_name)
            SOURCE KEY (regulation_id) REFERENCES Regulations (id)
            DESTINATION KEY (domain_name) REFERENCES Domains (name),
          ClauseDomains
            KEY (clause_id, domain_name)
            SOURCE KEY (clause_id) REFERENCES Clauses (id)
            DESTINATION KEY (domain_name) REFERENCES Domains (name)
        )
    EOT
    ,
  ]
}
