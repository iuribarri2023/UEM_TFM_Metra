"""Versioned REST registration. Domain routes keep stable blueprint endpoint names."""
from .api_support import (ApiError, api, document_policy, ifc_file_state,
                          publish_legacy_generic, publish_legacy_product)
from . import component_links, documents, economics
from .routes import admin, assets, auth, catalogue, comparison, cost_imports, manufacturer, templates
