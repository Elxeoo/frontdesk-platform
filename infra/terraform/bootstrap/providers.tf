provider "azurerm" {
  features {}
  storage_use_azuread = true

  subscription_id = var.subscription_id

  # AzureRM 5.x registers nothing by default. List every provider the project
  # needs here: the pipeline identity has no rights to register them.
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.Storage",
    "Microsoft.Consumption",
    "Microsoft.ManagedIdentity",
    "Microsoft.Network",
  ]
}
