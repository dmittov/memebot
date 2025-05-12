resource "google_app_engine_application" "this" {
  project     = data.google_client_config.default.project
  location_id = data.google_client_config.default.region

  database_type = "CLOUD_FIRESTORE"
  feature_settings {
    split_health_checks = true
  }
}