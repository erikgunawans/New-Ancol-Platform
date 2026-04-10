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

variable "network_id" {
  description = "VPC network ID for private IP"
  type        = string
}

variable "private_vpc_connection" {
  description = "Private VPC connection dependency"
  type        = string
}

variable "tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro" # dev; use db-custom-2-8192 for prod
}

variable "availability_type" {
  description = "HA configuration: REGIONAL or ZONAL"
  type        = string
  default     = "ZONAL" # dev; use REGIONAL for prod
}

variable "disk_size_gb" {
  description = "Initial disk size in GB"
  type        = number
  default     = 20
}

variable "deletion_protection" {
  description = "Prevent accidental deletion"
  type        = bool
  default     = true
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "ancol_compliance"
}

variable "database_user" {
  description = "Database user"
  type        = string
  default     = "ancol"
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}
