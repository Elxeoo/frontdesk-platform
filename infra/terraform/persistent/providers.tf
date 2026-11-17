provider "azurerm" {
  features {}

  subscription_id = var.subscription_id

  # Bootstrap registers resource providers; the pipeline identity has no rights to.
  resource_provider_registrations = "none"
}
