# Dev environment configuration
# NOTE: Sensitive values (database_password, billing_account_id) should be
# set via environment variables or a .tfvars file NOT checked into git:
#   export TF_VAR_database_password="..."
#   export TF_VAR_billing_account_id="..."

project_id  = "ancol-mom-compliance-dev"
region      = "asia-southeast2"
alert_email = "compliance-alerts@ancol.co.id"
