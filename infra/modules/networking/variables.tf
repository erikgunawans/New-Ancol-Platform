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

variable "subnet_cidr" {
  description = "CIDR range for the primary subnet"
  type        = string
  default     = "10.0.0.0/20"
}

variable "connector_cidr" {
  description = "CIDR range for the VPC Access connector"
  type        = string
  default     = "10.8.0.0/28"
}
