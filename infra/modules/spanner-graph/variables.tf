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
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "processing_units" {
  description = "Spanner processing units (100 = 1 node)"
  type        = number
  default     = 100
}
