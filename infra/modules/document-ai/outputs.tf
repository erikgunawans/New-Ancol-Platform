output "processor_id" {
  description = "Document AI processor ID"
  value       = google_document_ai_processor.form_parser.id
}

output "processor_name" {
  description = "Document AI processor name"
  value       = google_document_ai_processor.form_parser.name
}
