output "datastore_id" {
  description = "Vertex AI Search datastore ID"
  value       = google_discovery_engine_data_store.regulatory_corpus.data_store_id
}

output "datastore_name" {
  description = "Vertex AI Search datastore full resource name"
  value       = google_discovery_engine_data_store.regulatory_corpus.name
}

output "search_engine_id" {
  description = "Vertex AI Search engine ID"
  value       = google_discovery_engine_search_engine.regulatory_search.engine_id
}

output "contract_datastore_id" {
  description = "Contract clauses datastore ID"
  value       = google_discovery_engine_data_store.contract_clauses.data_store_id
}

output "contract_datastore_name" {
  description = "Contract clauses datastore full resource name"
  value       = google_discovery_engine_data_store.contract_clauses.name
}

output "contract_search_engine_id" {
  description = "Contract search engine ID"
  value       = google_discovery_engine_search_engine.contract_search.engine_id
}
