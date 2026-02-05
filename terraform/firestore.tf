variable "ttl_collections" {
  type    = set(string)
  default = [
    "allow_users",
    "llm_requests",
    "messages",
    "message_authors",
    "posts",
    "reactions"
    ]
}

resource "google_firestore_field" "ttl" {
  for_each = var.ttl_collections

  project    = data.google_client_config.default.project
  collection = each.value
  field      = "expiresAt"

  ttl_config {}
}
