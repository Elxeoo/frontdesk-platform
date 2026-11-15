data "azurerm_subscription" "current" {}

# Subscription scope, so AKS node resource groups (MC_*) are covered too.
resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "budget-frontdesk-monthly"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 25
  time_grain      = "Monthly"

  time_period {
    start_date = "2026-11-01T00:00:00Z"
  }

  notification {
    threshold      = 50
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.budget_contact_email]
  }

  notification {
    threshold      = 80
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.budget_contact_email]
  }

  notification {
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.budget_contact_email]
  }

  notification {
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_emails = [var.budget_contact_email]
  }
}
