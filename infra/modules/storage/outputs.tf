output "raw_bucket_name" {
  description = "Name of the raw documents bucket"
  value       = google_storage_bucket.raw.name
}

output "raw_bucket_url" {
  description = "URL of the raw documents bucket"
  value       = google_storage_bucket.raw.url
}

output "processed_bucket_name" {
  description = "Name of the processed documents bucket"
  value       = google_storage_bucket.processed.name
}

output "processed_bucket_url" {
  description = "URL of the processed documents bucket"
  value       = google_storage_bucket.processed.url
}

output "reports_bucket_name" {
  description = "Name of the reports bucket"
  value       = google_storage_bucket.reports.name
}

output "reports_bucket_url" {
  description = "URL of the reports bucket"
  value       = google_storage_bucket.reports.url
}

output "contracts_bucket_name" {
  description = "Name of the contracts bucket"
  value       = google_storage_bucket.contracts.name
}

output "contracts_bucket_url" {
  description = "URL of the contracts bucket"
  value       = google_storage_bucket.contracts.url
}
