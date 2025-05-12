locals {
  project_id = "memebot-459222"
  region     = "europe-west3"
}

inputs = {
  project_id = local.project_id
  region     = local.region
}

generate "backend" {
    path      = "backend.tf"
    if_exists = "overwrite"
    contents  = <<EOF
terraform{
    backend "gcs" {
        bucket = "${local.project_id}-tf-state"
        prefix = "."
    }
}
EOF
}

generate "provider" {
    path      = "provider.tf"
    if_exists = "overwrite"
    contents  = <<EOF
provider "google" {
  project = "${local.project_id}"
  region  = "${local.region}"
}
EOF
}