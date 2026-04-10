output "kms_key_id" {
  description = "Cloud KMS crypto key ID for data encryption"
  value       = google_kms_crypto_key.data_key.id
}

output "kms_keyring_id" {
  description = "Cloud KMS keyring ID"
  value       = google_kms_key_ring.main.id
}

output "service_account_emails" {
  description = "Map of service name to service account email"
  value = {
    for k, v in google_service_account.agents : k => v.email
  }
}

output "security_policy_id" {
  description = "Cloud Armor security policy ID"
  value       = google_compute_security_policy.main.id
}

output "db_password_secret_id" {
  description = "Secret Manager secret ID for DB password"
  value       = google_secret_manager_secret.db_password.id
}

output "sendgrid_secret_id" {
  description = "Secret Manager secret ID for SendGrid API key"
  value       = google_secret_manager_secret.sendgrid_api_key.id
}
