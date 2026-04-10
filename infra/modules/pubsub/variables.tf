variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "prefix" {
  description = "Resource naming prefix"
  type        = string
  default     = "ancol"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "push_endpoints" {
  description = "Map of service name to Cloud Run push endpoint URL"
  type        = map(string)
  default     = {}
}

variable "push_service_account_email" {
  description = "Service account email for OIDC token on push subscriptions"
  type        = string
  default     = ""
}
