variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-southeast2"
}

variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "email_ingest_url" {
  description = "Email Ingest Cloud Run service URL"
  type        = string
}

variable "regulation_monitor_url" {
  description = "Regulation Monitor Cloud Run service URL"
  type        = string
}

variable "api_gateway_url" {
  description = "API Gateway Cloud Run service URL (required for obligation scheduler)"
  type        = string
}

variable "invoker_service_account_email" {
  description = "Service account email for OIDC token (must have invoker permission on target services)"
  type        = string
}
