output "topic_ids" {
  description = "Map of topic name to topic ID"
  value = {
    for k, v in google_pubsub_topic.main : k => v.id
  }
}

output "topic_names" {
  description = "Map of topic key to full topic name"
  value = {
    for k, v in google_pubsub_topic.main : k => v.name
  }
}

output "dlq_topic_ids" {
  description = "Map of DLQ topic name to topic ID"
  value = {
    for k, v in google_pubsub_topic.dlq : k => v.id
  }
}

output "subscription_ids" {
  description = "Map of push subscription name to ID"
  value = {
    for k, v in google_pubsub_subscription.push : k => v.id
  }
}

output "hitl_decided_subscription" {
  description = "Pull subscription ID for hitl-decided topic"
  value       = google_pubsub_subscription.hitl_decided_pull.id
}
