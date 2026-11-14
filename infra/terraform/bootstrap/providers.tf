provider "azurerm" {
  features {}

  subscription_id = var.subscription_id

  # AzureRM 5.x registers nothing by default; list only what bootstrap needs.
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.Storage",
    "Microsoft.Consumption",
    "Microsoft.ManagedIdentity",
  ]
}
