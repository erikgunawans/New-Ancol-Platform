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
