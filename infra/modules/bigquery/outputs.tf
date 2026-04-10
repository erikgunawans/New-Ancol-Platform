output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.compliance.dataset_id
}

output "audit_events_table_id" {
  description = "Audit events table ID"
  value       = google_bigquery_table.audit_events.table_id
}

output "compliance_scores_table_id" {
  description = "Compliance scores table ID"
  value       = google_bigquery_table.compliance_scores.table_id
}
