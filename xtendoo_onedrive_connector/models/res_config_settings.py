# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    onedrive_client_id = fields.Char(string="OneDrive Client ID", config_parameter="xtendoo_onedrive_connector.onedrive_client_id")
    onedrive_client_secret = fields.Char(string="OneDrive Client Secret", config_parameter="xtendoo_onedrive_connector.onedrive_client_secret")
    onedrive_tenant_id = fields.Char(string="OneDrive Tenant ID", config_parameter="xtendoo_onedrive_connector.onedrive_tenant_id")
    onedrive_redirect_uri = fields.Char(string="OneDrive Redirect URI", config_parameter="xtendoo_onedrive_connector.onedrive_redirect_uri")
    onedrive_refresh_token = fields.Char(string="OneDrive Refresh Token", config_parameter="xtendoo_onedrive_connector.onedrive_refresh_token")

    def action_get_onedrive_token(self):
        # Aquí se implementaría la lógica para obtener el token OAuth2
        pass


