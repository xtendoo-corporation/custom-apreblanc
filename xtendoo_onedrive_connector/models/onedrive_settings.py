from odoo import models, fields, api
import requests
import logging
import json

_logger = logging.getLogger(__name__)

class OneDriveSettings(models.Model):
    _name = 'onedrive.settings'
    _description = 'Configuración de OneDrive'
    _rec_name = 'onedrive_client_id'

    onedrive_client_id = fields.Char('Client ID', required=True)
    onedrive_client_secret = fields.Char('Client Secret', required=True)
    onedrive_tenant_id = fields.Char('Tenant ID', required=True)
    onedrive_redirect_uri = fields.Char('Redirect URI', required=True)
    onedrive_refresh_token = fields.Char('Refresh Token')
    onedrive_access_token = fields.Char('Access Token', readonly=True)
    onedrive_token_expiry = fields.Datetime('Token Expiry', readonly=True)

    def get_auth_url(self):
        base_url = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        if not (self.onedrive_client_id and self.onedrive_tenant_id and self.onedrive_redirect_uri):
            return False
        params = (
            f"client_id={self.onedrive_client_id}"
            f"&response_type=code"
            f"&redirect_uri={self.onedrive_redirect_uri}"
            f"&response_mode=query"
            f"&scope=offline_access Files.ReadWrite.All User.Read"
            f"&state=odoo_onedrive"
        )
        return base_url.format(tenant_id=self.onedrive_tenant_id) + "?" + params

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

    def save_refresh_token(self, code):
        """Guarda el token de refresco obtenido mediante el código de autorización"""
        if not code:
            return False

        # URL del token
        token_url = f"https://login.microsoftonline.com/{self.onedrive_tenant_id}/oauth2/v2.0/token"

        # Datos para la solicitud
        data = {
            'client_id': self.onedrive_client_id,
            'client_secret': self.onedrive_client_secret,
            'code': code,
            'redirect_uri': self.onedrive_redirect_uri,
            'grant_type': 'authorization_code',
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            self.onedrive_refresh_token = token_data.get('refresh_token')
            self.onedrive_access_token = token_data.get('access_token')

            # Guardar las modificaciones
            self.env.cr.commit()

            return True
        except Exception as e:
            _logger.error(f"Error al obtener el token de refresco: {str(e)}")
            return False

    def _refresh_access_token(self):
        """Refresca el token de acceso usando el token de refresco almacenado"""
        if not self.onedrive_refresh_token:
            return False

        # URL del token
        token_url = f"https://login.microsoftonline.com/{self.onedrive_tenant_id}/oauth2/v2.0/token"

        # Datos para la solicitud
        data = {
            'client_id': self.onedrive_client_id,
            'client_secret': self.onedrive_client_secret,
            'refresh_token': self.onedrive_refresh_token,
            'redirect_uri': self.onedrive_redirect_uri,
            'grant_type': 'refresh_token',
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            # Actualizar los tokens
            self.onedrive_access_token = token_data.get('access_token')

            # Si se proporciona un nuevo token de refresco, actualizarlo
            if token_data.get('refresh_token'):
                self.onedrive_refresh_token = token_data.get('refresh_token')

            return self.onedrive_access_token
        except Exception as e:
            _logger.error(f"Error al refrescar el token de acceso: {str(e)}")
            return False

    def test_connection(self):
        """Prueba la conexión con OneDrive usando el token de refresco"""
        if not self.onedrive_refresh_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No hay token de refresco configurado',
                    'type': 'danger',
                }
            }

        # Obtener un nuevo token de acceso
        access_token = self._refresh_access_token()
        if not access_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No se pudo obtener el token de acceso',
                    'type': 'danger',
                }
            }

        # Probar una llamada a la API de OneDrive
        api_url = "https://graph.microsoft.com/v1.0/me/drive"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            drive_info = response.json()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Éxito',
                    'message': f'Conexión exitosa a OneDrive. Espacio disponible: {drive_info.get("quota", {}).get("remaining", 0)} bytes',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Error al probar la conexión con OneDrive: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al conectar con OneDrive: {str(e)}',
                    'type': 'danger',
                }
            }
