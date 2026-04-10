output "workflow_id" {
  description = "Cloud Workflows workflow ID"
  value       = google_workflows_workflow.mom_compliance.id
}

output "workflow_name" {
  description = "Cloud Workflows workflow name"
  value       = google_workflows_workflow.mom_compliance.name
}

output "workflow_sa_email" {
  description = "Workflow service account email"
  value       = google_service_account.workflow.email
}
