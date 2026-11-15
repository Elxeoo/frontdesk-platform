data "azurerm_client_config" "current" {}

# Bootstrap runs locally; this grants the operator data access to the state container.
resource "azurerm_role_assignment" "tfstate_blob_contributor" {
  scope                = azurerm_storage_container.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
