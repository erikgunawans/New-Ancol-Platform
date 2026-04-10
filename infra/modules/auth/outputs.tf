output "iap_client_id" {
  description = "IAP OAuth client ID"
  value       = google_iap_client.main.client_id
}

output "iap_client_secret" {
  description = "IAP OAuth client secret"
  value       = google_iap_client.main.secret
  sensitive   = true
}
