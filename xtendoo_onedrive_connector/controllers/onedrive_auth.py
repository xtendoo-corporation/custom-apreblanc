from odoo import http
from odoo.http import request
import logging
import requests
_logger = logging.getLogger(__name__)

class OneDriveAuthController(http.Controller):
    @http.route('/onedrive/callback', type='http', auth='public', csrf=False)
    def onedrive_callback(self, **kwargs):
        # Log completo de todos los parámetros recibidos
        _logger.info(f"[OneDrive] Callback recibido con todos los parámetros: {kwargs}")

        code = kwargs.get('code')
        state = kwargs.get('state')
        error = kwargs.get('error')
        error_description = kwargs.get('error_description')

        _logger.info(f"[OneDrive] Parámetros extraídos - code: {code[:10] if code else 'None'}..., state: {state}, error: {error}, error_description: {error_description}")

        if error:
            _logger.error(f"[OneDrive] Error de autorización recibido: {error} - {error_description}")
            return f"Error de autorización: {error}<br>Descripción: {error_description}<br><br>Revisa la configuración en Azure Portal."

        if not code:
            _logger.error(f"[OneDrive] No se recibió código. Todos los parámetros: {kwargs}")
            return """
            <h2>No se recibió ningún código de autorización</h2>
            <p><strong>Parámetros recibidos:</strong> {}</p>
            <p><strong>Posibles causas:</strong></p>
            <ul>
                <li>La URL de redirección en Azure Portal no coincide exactamente con: <code>https://pre-apreblanc.xtendoo.es/onedrive/callback</code></li>
                <li>Los permisos de la aplicación no están configurados correctamente</li>
                <li>El usuario canceló la autorización</li>
            </ul>
            <p><strong>Verifica en Azure Portal:</strong></p>
            <ol>
                <li>Ve a tu aplicación en Azure Portal</li>
                <li>En "Authentication" > "Redirect URIs", asegúrate de que esté exactamente: <code>https://pre-apreblanc.xtendoo.es/onedrive/callback</code></li>
                <li>En "API permissions", verifica que tengas: Files.ReadWrite.All (Delegated)</li>
                <li>Asegúrate de haber dado "Grant admin consent"</li>
            </ol>
            <p><a href="javascript:history.back()">Volver</a></p>
            """.format(str(kwargs))

        # Obtener configuración de OneDrive
        settings = request.env['onedrive.settings'].sudo().search([], limit=1)
        if not settings:
            return "Error: No se encontró configuración de OneDrive."

        # Intercambiar código por refresh_token
        try:
            token_url = f"https://login.microsoftonline.com/{settings.onedrive_tenant_id}/oauth2/v2.0/token"
            token_data = {
                'client_id': settings.onedrive_client_id,
                'client_secret': settings.onedrive_client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': settings.onedrive_redirect_uri,
                'scope': 'openid offline_access files.readwrite.all',  # Scopes compatibles
            }

            _logger.info(f"[OneDrive] Intercambiando código por token. URL: {token_url}")

            response = requests.post(token_url, data=token_data, timeout=30)

            _logger.info(f"[OneDrive] Respuesta del intercambio: {response.status_code}")

            if response.status_code == 200:
                token_response = response.json()
                refresh_token = token_response.get('refresh_token')
                access_token = token_response.get('access_token')

                if refresh_token:
                    # Guardar refresh_token en la configuración
                    settings.sudo().write({'onedrive_refresh_token': refresh_token})
                    _logger.info(f"[OneDrive] Refresh token guardado exitosamente")

                    return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {
                        'success': True,
                        'message': '¡Autorización exitosa! OneDrive está ahora configurado correctamente.',
                        'refresh_token_preview': refresh_token[:20] + '...' if refresh_token else None
                    })
                else:
                    _logger.error(f"[OneDrive] No se recibió refresh_token: {token_response}")
                    return f"Error: No se recibió refresh_token. Respuesta: {token_response}"
            else:
                error_response = response.json() if response.content else {}
                _logger.error(f"[OneDrive] Error intercambiando código: {response.status_code} - {error_response}")
                return f"Error intercambiando código: {response.status_code} - {error_response.get('error_description', 'Error desconocido')}"

        except Exception as e:
            _logger.error(f"[OneDrive] Excepción durante intercambio: {str(e)}")
            return f"Error procesando autorización: {str(e)}"
