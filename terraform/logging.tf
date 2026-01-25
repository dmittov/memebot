# Cloud Storage bucket for application logs
resource "google_storage_bucket" "logs" {
  name     = "${data.google_client_config.default.project}-app-logs"
  location = "EU"
  project  = data.google_client_config.default.project

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 365 # Delete logs older than 365 days
    }
    action {
      type = "Delete"
    }
  }
}

# Log Sink to export stderr logs to Cloud Storage
resource "google_logging_project_sink" "stderr_to_gcs" {
  name        = "stderr-to-gcs"
  project     = data.google_client_config.default.project
  destination = "storage.googleapis.com/${google_storage_bucket.logs.name}"

  filter = "logName=\"projects/${data.google_client_config.default.project}/logs/stderr\""

  unique_writer_identity = true
}

# Grant the Log Sink service account write access to the bucket
resource "google_storage_bucket_iam_member" "log_sink_writer" {
  bucket = google_storage_bucket.logs.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.stderr_to_gcs.writer_identity
}
