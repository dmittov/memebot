resource "google_project_iam_custom_role" "memebot_role" {
  project     = data.google_client_config.default.project

  role_id     = "memeBot"
  title       = "App Engine Meme Bot role"

  permissions = [
    "datastore.databases.get",
    "datastore.entities.get",
    "datastore.entities.list",
    "datastore.entities.create",
    "datastore.entities.update",
    "datastore.entities.delete",

    "pubsub.topics.publish",

    "cloudtasks.tasks.create",
  ]
}

resource "google_project_iam_member" "bind_runtime_role" {
  project = data.google_client_config.default.project
  role    = google_project_iam_custom_role.memebot_role.name
  member  = "serviceAccount:${data.google_client_config.default.project}@appspot.gserviceaccount.com"
}

resource "google_project_iam_member" "strip_editor" {
  project = data.google_client_config.default.project
  role    = "roles/editor"
  member  = "serviceAccount:${data.google_client_config.default.project}@appspot.gserviceaccount.com"

  lifecycle {
    prevent_destroy = false
    ignore_changes  = [role, member]
  }
}

resource "google_storage_bucket_iam_member" "main_bucket_access" {
  bucket = "memebot-459222.appspot.com"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_client_config.default.project}@appspot.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "staging_bucket_access" {
  bucket = "staging.memebot-459222.appspot.com"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_client_config.default.project}@appspot.gserviceaccount.com"
}

resource "google_project_iam_member" "secret_accessor" {
  project = data.google_client_config.default.project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_client_config.default.project}@appspot.gserviceaccount.com"
}
