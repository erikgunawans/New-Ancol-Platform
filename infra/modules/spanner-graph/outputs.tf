output "instance_name" {
  description = "Spanner instance name"
  value       = google_spanner_instance.main.name
}

output "database_name" {
  description = "Spanner database name"
  value       = google_spanner_database.regulations.name
}

output "instance_id" {
  description = "Full Spanner instance ID"
  value       = google_spanner_instance.main.id
}
