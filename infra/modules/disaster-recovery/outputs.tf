output "replica_instance_name" {
  value       = google_sql_database_instance.replica.name
  description = "DR replica instance name"
}

output "replica_connection_name" {
  value       = google_sql_database_instance.replica.connection_name
  description = "DR replica connection name"
}

output "raw_dr_bucket" {
  value       = google_storage_bucket.raw_dr.name
  description = "DR raw documents bucket"
}

output "reports_dr_bucket" {
  value       = google_storage_bucket.reports_dr.name
  description = "DR reports bucket"
}
