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

variable "raw_bucket_name" {
  description = "Name of the raw documents bucket (for Eventarc trigger)"
  type        = string
}

variable "document_processor_service_name" {
  description = "Cloud Run service name for the document processor"
  type        = string
}

variable "trigger_service_account_email" {
  description = "Service account for Eventarc trigger"
  type        = string
}
