variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "project_number" {
  description = "GCP project number"
  type        = string
}

variable "support_email" {
  description = "Support email for IAP consent screen"
  type        = string
}

variable "authorized_members" {
  description = "List of IAM members authorized to access via IAP"
  type        = list(string)
  default     = []
}
