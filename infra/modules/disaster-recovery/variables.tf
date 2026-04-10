variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "dr_region" {
  description = "DR region for cross-region replication"
  type        = string
  default     = "asia-southeast1" # Singapore — closest to Jakarta
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "primary_db_instance_name" {
  description = "Primary Cloud SQL instance name for replica"
  type        = string
}

variable "vpc_network_id" {
  description = "VPC network self_link for private IP"
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine type for replica"
  type        = string
  default     = "db-custom-2-7680"
}

variable "db_disk_size_gb" {
  description = "Disk size for DR replica"
  type        = number
  default     = 50
}

variable "kms_key_id" {
  description = "KMS key for bucket encryption"
  type        = string
}

variable "bucket_raw" {
  description = "Source raw documents bucket name"
  type        = string
}

variable "bucket_reports" {
  description = "Source reports bucket name"
  type        = string
}

variable "notification_channels" {
  description = "Monitoring notification channel IDs"
  type        = list(string)
}
