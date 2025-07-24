from odoo import models, fields, api
import urllib.parse

class OneDriveSettings(models.Model):
    _name = 'onedrive.settings'
    _description = 'Configuración de OneDrive'
    _rec_name = 'onedrive_client_id'

    onedrive_client_id = fields.Char('Client ID', required=True)
    onedrive_client_secret = fields.Char('Client Secret', required=True)
    onedrive_tenant_id = fields.Char('Tenant ID', required=True)
    onedrive_redirect_uri = fields.Char('Redirect URI', required=True)
    onedrive_refresh_token = fields.Char('Refresh Token')

    def get_auth_url(self):
        # Usar endpoint común en lugar de tenant específico para cuentas personales
        base_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        if not (self.onedrive_client_id and self.onedrive_redirect_uri):
            return False

        # Definir scopes para OneDrive Personal y Business (más compatible)
        scopes = "openid offline_access Files.ReadWrite.All"
        encoded_scopes = urllib.parse.quote(scopes)
        encoded_redirect_uri = urllib.parse.quote(self.onedrive_redirect_uri)

        params = (
            f"client_id={self.onedrive_client_id}"
            f"&response_type=code"
            f"&redirect_uri={encoded_redirect_uri}"
            f"&response_mode=query"
            f"&scope={encoded_scopes}"
            f"&state=odoo_onedrive"
        )
        return base_url + "?" + params

    def action_get_onedrive_auth_url(self):
        url = self.get_auth_url()
        if url:
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Faltan datos',
                    'message': 'Debes rellenar Client ID, Tenant ID y Redirect URI.',
                    'type': 'warning',
                }
            }
