# Terraform state stored in GCS
# Create this bucket manually before first terraform init:
#   gsutil mb -l asia-southeast2 gs://ancol-terraform-state
#   gsutil versioning set on gs://ancol-terraform-state

# The backend config is in main.tf:
#   backend "gcs" {
#     bucket = "ancol-terraform-state"
#     prefix = "dev"
#   }
