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
            return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {
                'code': False,  # Usar el parámetro que espera la plantilla
            })

        # Obtener configuración de OneDrive
        settings = request.env['onedrive.settings'].sudo().search([], limit=1)
        if not settings:
            return "Error: No se encontró configuración de OneDrive."

        # Intercambiar código por refresh_token
        try:
            # Usar endpoint común para cuentas personales y empresariales
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            token_data = {
                'client_id': settings.onedrive_client_id,
                'client_secret': settings.onedrive_client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': settings.onedrive_redirect_uri,
                'scope': 'openid offline_access Files.ReadWrite.All',  # Corregir scopes con mayúsculas
            }

            _logger.info(f"[OneDrive] Intercambiando código por token. URL: {token_url}")
            _logger.info(f"[OneDrive] Datos enviados (sin secretos): client_id={settings.onedrive_client_id}, grant_type=authorization_code, scope=openid offline_access Files.ReadWrite.All")

            response = requests.post(token_url, data=token_data, timeout=30)

            _logger.info(f"[OneDrive] Respuesta del intercambio: {response.status_code}")
            _logger.info(f"[OneDrive] Headers de respuesta: {dict(response.headers)}")

            if response.status_code == 200:
                token_response = response.json()
                refresh_token = token_response.get('refresh_token')
                access_token = token_response.get('access_token')

                _logger.info(f"[OneDrive] Token response keys: {list(token_response.keys())}")

                if refresh_token:
                    # Guardar refresh_token en la configuración
                    settings.sudo().write({'onedrive_refresh_token': refresh_token})
                    _logger.info(f"[OneDrive] Refresh token guardado exitosamente")

                    # Verificar que el token funciona haciendo una llamada de prueba
                    try:
                        test_headers = {'Authorization': f'Bearer {access_token}'}
                        test_response = requests.get('https://graph.microsoft.com/v1.0/me', headers=test_headers, timeout=10)
                        if test_response.status_code == 200:
                            user_info = test_response.json()
                            user_email = user_info.get('userPrincipalName', user_info.get('mail', 'Usuario'))
                            _logger.info(f"[OneDrive] Verificación exitosa para usuario: {user_email}")
                        else:
                            _logger.warning(f"[OneDrive] Verificación falló: {test_response.status_code}")
                    except Exception as test_error:
                        _logger.warning(f"[OneDrive] No se pudo verificar el token: {test_error}")

                    return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {
                        'success': True,
                        'message': '¡Autorización exitosa! OneDrive está ahora configurado correctamente.',
                        'refresh_token_preview': refresh_token[:20] + '...' if refresh_token else None
                    })
                else:
                    _logger.error(f"[OneDrive] No se recibió refresh_token: {token_response}")
                    return f"Error: No se recibió refresh_token. Respuesta completa: {token_response}"
            else:
                try:
                    error_response = response.json()
                except:
                    error_response = {'error': 'unknown', 'error_description': response.text}

                _logger.error(f"[OneDrive] Error intercambiando código: {response.status_code} - {error_response}")

                # Manejar errores específicos
                if error_response.get('error') == 'invalid_grant':
                    return """
                    <h2>Error: Código de autorización inválido o expirado</h2>
                    <p>El código de autorización puede haber expirado. Los códigos de autorización tienen una validez muy corta (normalmente 10 minutos).</p>
                    <p><strong>Solución:</strong> Vuelve a la configuración de OneDrive y genera un nuevo código de autorización.</p>
                    <p><a href="javascript:window.close()">Cerrar esta ventana</a></p>
                    """
                elif error_response.get('error') == 'invalid_client':
                    return """
                    <h2>Error: Credenciales de cliente inválidas</h2>
                    <p>El Client ID o Client Secret no son correctos.</p>
                    <p><strong>Verifica en Azure Portal:</strong></p>
                    <ul>
                        <li>Client ID debe coincidir exactamente</li>
                        <li>Client Secret debe estar activo y no expirado</li>
                        <li>La aplicación debe estar configurada para cuentas multitenant</li>
                    </ul>
                    <p><a href="javascript:window.close()">Cerrar esta ventana</a></p>
                    """
                else:
                    return f"""
                    <h2>Error intercambiando código de autorización</h2>
                    <p><strong>Status:</strong> {response.status_code}</p>
                    <p><strong>Error:</strong> {error_response.get('error', 'desconocido')}</p>
                    <p><strong>Descripción:</strong> {error_response.get('error_description', 'No disponible')}</p>
                    <p><a href="javascript:window.close()">Cerrar esta ventana</a></p>
                    """

        except Exception as e:
            _logger.error(f"[OneDrive] Excepción durante intercambio: {str(e)}")
            return f"""
            <h2>Error procesando autorización</h2>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Revisa los logs del servidor para más detalles.</p>
            <p><a href="javascript:window.close()">Cerrar esta ventana</a></p>
            """
