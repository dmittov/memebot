resource "google_project_service" "required_apis" {
  for_each = toset([
    "appengine.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  project                    = data.google_client_config.default.project
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}
