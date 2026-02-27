from odoo import http
from odoo.http import request
import logging
import requests
import json
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
                'code': False,
                'success': False,
                'verify_error': False,
                'user_email': '',
            })

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
                'scope': 'openid offline_access Files.ReadWrite.All',
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

                verify_error = False
                user_email = ''
                if refresh_token:
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
                            verify_error = True
                    except Exception as test_error:
                        _logger.warning(f"[OneDrive] No se pudo verificar el token: {test_error}")
                        verify_error = True

                    # Mostrar mensaje de éxito o advertencia según la verificación
                    return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {
                        'code': code,
                        'success': True,
                        'verify_error': verify_error,
                        'user_email': user_email,
                    })
                else:
                    return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {
                        'code': code,
                        'success': False,
                        'verify_error': True,
                        'user_email': '',
                    })
            else:
                _logger.error(f"[OneDrive] Error al intercambiar código por token: {response.text}")
                return f"Error al intercambiar código por token: {response.text}"
        except Exception as e:
            _logger.error(f"[OneDrive] Excepción durante el intercambio de código: {e}")
            return f"Excepción durante el intercambio de código: {e}"

    @http.route('/onedrive/debug', type='http', auth='user')
    def onedrive_debug(self):
        """Controlador de diagnóstico para OneDrive"""
        try:
            # Obtener la configuración actual
            settings = request.env['onedrive.settings'].sudo().search([], limit=1)
            if not settings:
                return "<h1>Error: No se ha encontrado configuración de OneDrive</h1>"

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # Verificar si la URL de redirección coincide con la configuración base de Odoo
            redirect_uri_match = settings.onedrive_redirect_uri == f"{base_url}/onedrive/callback"

            # Generar URL de autorización para pruebas directas
            auth_url = settings.get_auth_url() if settings else "No se pudo generar URL"

            # Construir la respuesta HTML con la información de diagnóstico
            html = f"""
            <html>
                <head>
                    <title>Diagnóstico OneDrive</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                        h1 {{ color: #1e88e5; }}
                        h2 {{ color: #0d47a1; margin-top: 30px; }}
                        .section {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                        .warning {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeeba; }}
                        .error {{ background-color: #f8d7da; padding: 15px; border-radius: 5px; border: 1px solid #f5c6cb; }}
                        .success {{ background-color: #d4edda; padding: 15px; border-radius: 5px; border: 1px solid #c3e6cb; }}
                        .btn {{ display: inline-block; background-color: #1e88e5; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin-top: 15px; }}
                        table {{ width: 100%; border-collapse: collapse; }}
                        table, th, td {{ border: 1px solid #ddd; }}
                        th, td {{ padding: 10px; text-align: left; }}
                        th {{ background-color: #f2f2f2; }}
                        code {{ background-color: #f5f5f5; padding: 2px 4px; border-radius: 3px; }}
                    </style>
                </head>
                <body>
                    <h1>Diagnóstico de OneDrive</h1>

                    <div class="section">
                        <h2>Configuración actual</h2>
                        <table>
                            <tr>
                                <th>Parámetro</th>
                                <th>Valor</th>
                                <th>Estado</th>
                            </tr>
                            <tr>
                                <td>Client ID</td>
                                <td>{settings.onedrive_client_id[:5]}...{settings.onedrive_client_id[-5:] if settings.onedrive_client_id else ''}</td>
                                <td>{'✅' if settings.onedrive_client_id else '❌ Falta'}</td>
                            </tr>
                            <tr>
                                <td>Client Secret</td>
                                <td>{'Configurado' if settings.onedrive_client_secret else 'No configurado'}</td>
                                <td>{'✅' if settings.onedrive_client_secret else '❌ Falta'}</td>
                            </tr>
                            <tr>
                                <td>Tenant ID</td>
                                <td>{settings.onedrive_tenant_id[:5]}...{settings.onedrive_tenant_id[-5:] if settings.onedrive_tenant_id else ''}</td>
                                <td>{'✅' if settings.onedrive_tenant_id else '❌ Falta'}</td>
                            </tr>
                            <tr>
                                <td>Redirect URI</td>
                                <td>{settings.onedrive_redirect_uri}</td>
                                <td>{'✅' if settings.onedrive_redirect_uri else '❌ Falta'}</td>
                            </tr>
                            <tr>
                                <td>Refresh Token</td>
                                <td>{'Configurado' if settings.onedrive_refresh_token else 'No configurado'}</td>
                                <td>{'✅' if settings.onedrive_refresh_token else '⚠️ Pendiente'}</td>
                            </tr>
                        </table>
                    </div>

                    <div class="section">
                        <h2>Información del entorno</h2>
                        <table>
                            <tr><th>Parámetro</th><th>Valor</th></tr>
                            <tr><td>URL base de Odoo</td><td>{base_url}</td></tr>
                            <tr><td>URL de callback esperada</td><td>{base_url}/onedrive/callback</td></tr>
                            <tr>
                                <td>¿Coincide con la configurada?</td>
                                <td class="{'success' if redirect_uri_match else 'error'}">{
                                    '✅ Sí' if redirect_uri_match else f'❌ No - La URL de redirección configurada ({settings.onedrive_redirect_uri}) no coincide con la esperada ({base_url}/onedrive/callback)'
                                }</td>
                            </tr>
                        </table>
                    </div>

                    <div class="{'warning' if not redirect_uri_match else 'section'}">
                        <h2>Verificación de configuración en Azure</h2>
                        <p>Asegúrate de que la configuración de Azure coincide exactamente con estos valores:</p>
                        <ul>
                            <li>Tipo de cuenta compatible: <strong>Accounts in this organizational directory only (Single tenant)</strong></li>
                            <li>Redirect URI: <strong>{settings.onedrive_redirect_uri}</strong></li>
                            <li>Permisos de la API: <strong>Files.ReadWrite.All, offline_access</strong></li>
                        </ul>
                        <p><strong>¿Problemas comunes?</strong></p>
                        <ul>
                            <li>Redirección HTTP vs HTTPS (debe coincidir exactamente)</li>
                            <li>Barras al final de la URL (si tienes o no tienes / al final)</li>
                            <li>Permisos insuficientes o no concedidos</li>
                            <li>Client Secret expirado</li>
                        </ul>
                    </div>

                    <div class="section">
                        <h2>Prueba de autenticación</h2>
                        <p>Haz clic en el botón para iniciar una nueva prueba de autenticación:</p>
                        <a href="{auth_url}" class="btn" target="_blank">Iniciar autenticación con OneDrive</a>
                    </div>

                    <div class="section">
                        <h2>Información para soporte</h2>
                        <p>Si el problema persiste, proporciona esta información al soporte técnico:</p>
                        <ul>
                            <li>URL base: {base_url}</li>
                            <li>Tenant ID: {settings.onedrive_tenant_id[:5]}...{settings.onedrive_tenant_id[-5:] if settings.onedrive_tenant_id else ''}</li>
                            <li>Application ID: {settings.onedrive_client_id[:5]}...{settings.onedrive_client_id[-5:] if settings.onedrive_client_id else ''}</li>
                            <li>Redirect URI: {settings.onedrive_redirect_uri}</li>
                        </ul>
                    </div>
                </body>
            </html>
            """
            return html

        except Exception as e:
            return f"<h1>Error al generar diagnóstico</h1><p>Detalles: {str(e)}</p>"
