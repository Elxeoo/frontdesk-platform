variable "subscription_id" {
  description = "Azure subscription to deploy into. Set it with the TF_VAR_subscription_id environment variable."
  type        = string
}

variable "budget_contact_email" {
  description = "Recipient of budget alerts. Set it with the TF_VAR_budget_contact_email environment variable."
  type        = string
}
