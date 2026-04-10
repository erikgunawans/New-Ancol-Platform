variable "project_name" {
  description = "Display name for the GCP project"
  type        = string
  default     = "Ancol MoM Compliance"
}

variable "project_id" {
  description = "Unique GCP project ID"
  type        = string
}

variable "org_id" {
  description = "GCP Organization ID"
  type        = string
  default     = ""
}

variable "billing_account_id" {
  description = "GCP Billing Account ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}
