variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-southeast2"
}

variable "billing_account_id" {
  description = "GCP Billing Account ID"
  type        = string
}

variable "database_password" {
  description = "PostgreSQL database password"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email for monitoring alerts"
  type        = string
}

variable "support_email" {
  description = "Support email for IAP consent screen"
  type        = string
  default     = ""
}

variable "authorized_members" {
  description = "IAM members authorized for IAP access"
  type        = list(string)
  default     = []
}
