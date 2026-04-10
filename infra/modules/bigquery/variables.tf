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
  description = "Resource naming prefix"
  type        = string
  default     = "ancol"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "audit_writer_sa_email" {
  description = "Service account email that writes audit events"
  type        = string
}
