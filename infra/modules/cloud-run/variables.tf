variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-southeast2"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
}

variable "image" {
  description = "Container image URL"
  type        = string
  default     = "gcr.io/cloudrun/placeholder" # Replaced at deploy time
}

variable "service_account_email" {
  description = "Service account email for this service"
  type        = string
}

variable "vpc_connector_id" {
  description = "VPC Access connector ID"
  type        = string
}

variable "port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "cpu" {
  description = "CPU limit"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit"
  type        = string
  default     = "512Mi"
}

variable "cpu_idle" {
  description = "Allow CPU to be throttled when idle"
  type        = bool
  default     = true
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "request_timeout" {
  description = "Request timeout"
  type        = string
  default     = "300s"
}

variable "ingress" {
  description = "Ingress setting"
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

variable "env_vars" {
  description = "List of environment variables"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "secret_env_vars" {
  description = "List of secret environment variables from Secret Manager"
  type = list(object({
    name      = string
    secret_id = string
  }))
  default = []
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access (for IAP-fronted services)"
  type        = bool
  default     = false
}

variable "push_invoker_sa" {
  description = "Service account allowed to invoke via Pub/Sub push"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}
