output "api_gateway_url" {
  description = "API Gateway Cloud Run URL"
  value       = module.run_api_gateway.service_url
}

output "web_frontend_url" {
  description = "Web Frontend Cloud Run URL"
  value       = module.run_web_frontend.service_url
}

output "database_connection_name" {
  description = "Cloud SQL connection name (for Cloud SQL Proxy)"
  value       = module.database.instance_connection_name
}

output "database_private_ip" {
  description = "Cloud SQL private IP address"
  value       = module.database.private_ip_address
}
