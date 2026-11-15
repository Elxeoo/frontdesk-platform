resource "azurerm_resource_group" "dev" {
  name     = "rg-frontdesk-dev"
  location = azurerm_resource_group.tfstate.location
  tags     = azurerm_resource_group.tfstate.tags
}

resource "azurerm_user_assigned_identity" "pipeline" {
  name                = "id-frontdesk-pipeline"
  resource_group_name = azurerm_resource_group.tfstate.name
  location            = azurerm_resource_group.tfstate.location
  tags                = azurerm_resource_group.tfstate.tags
}

# principal_type avoids lookup failures right after the identity is created.
resource "azurerm_role_assignment" "pipeline_dev_contributor" {
  scope                = azurerm_resource_group.dev.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "pipeline_dev_rbac_admin" {
  scope                = azurerm_resource_group.dev.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "pipeline_tfstate_blob" {
  scope                = azurerm_storage_container.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
  principal_type       = "ServicePrincipal"
}
