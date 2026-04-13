output "email_scan_job_name" {
  description = "Cloud Scheduler job name for email scanning"
  value       = google_cloud_scheduler_job.email_scan.name
}

output "regulation_check_job_name" {
  description = "Cloud Scheduler job name for regulation checking"
  value       = google_cloud_scheduler_job.regulation_check.name
}
