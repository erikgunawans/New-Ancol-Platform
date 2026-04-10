output "network_id" {
  description = "VPC network ID"
  value       = google_compute_network.main.id
}

output "network_name" {
  description = "VPC network name"
  value       = google_compute_network.main.name
}

output "subnet_id" {
  description = "Primary subnet ID"
  value       = google_compute_subnetwork.primary.id
}

output "subnet_name" {
  description = "Primary subnet name"
  value       = google_compute_subnetwork.primary.name
}

output "vpc_connector_id" {
  description = "VPC Access connector ID for Cloud Run"
  value       = google_vpc_access_connector.serverless.id
}

output "vpc_connector_name" {
  description = "VPC Access connector name"
  value       = google_vpc_access_connector.serverless.name
}

output "private_vpc_connection" {
  description = "Private VPC connection for Cloud SQL"
  value       = google_service_networking_connection.private_vpc.id
}
