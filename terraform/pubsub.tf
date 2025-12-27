resource "google_pubsub_topic" "topic_explain" {
  name = "explain"
  message_retention_duration = "604800s" # 7 days
}

resource "google_pubsub_subscription" "sub_explain" {
  name  = "sub-explain-pull"
  topic = google_pubsub_topic.topic_explain.name

  ack_deadline_seconds         = 600
  retain_acked_messages        = false
  enable_exactly_once_delivery = true
}

resource "google_pubsub_topic" "topic_message" {
  name = "message"
  message_retention_duration = "604800s" # 7 days
}

resource "google_pubsub_subscription" "sub_message" {
  name  = "sub-message-pull"
  topic = google_pubsub_topic.topic_message.name

  ack_deadline_seconds         = 600
  retain_acked_messages        = false
  enable_exactly_once_delivery = true
}
