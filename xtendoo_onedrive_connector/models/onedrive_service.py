# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)

class OneDriveService(models.AbstractModel):
    _name = 'onedrive.service'
    _description = 'Servicio de conexión con OneDrive'

    def _get_config(self):
        # Obtener configuración desde el modelo onedrive.settings
        settings = self.env['onedrive.settings'].search([], limit=1)
        if not settings:
            return {
                'client_id': None,
                'client_secret': None,
                'tenant_id': None,
                'redirect_uri': None,
                'refresh_token': None,
            }

        return {
            'client_id': settings.onedrive_client_id,
            'client_secret': settings.onedrive_client_secret,
            'tenant_id': settings.onedrive_tenant_id,
            'redirect_uri': settings.onedrive_redirect_uri,
            'refresh_token': settings.onedrive_refresh_token,
        }

    def _get_token(self):
        config = self._get_config()

        # Validar configuración más detalladamente
        missing_params = []
        for key, value in config.items():
            if not value:
                missing_params.append(key)

        if missing_params:
            _logger.error('Faltan parámetros de configuración de OneDrive: %s', ', '.join(missing_params))
            raise UserError(_('Faltan credenciales de OneDrive: %s') % ', '.join(missing_params))

        # Usar endpoint común para cuentas personales y empresariales
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': config['refresh_token'],
            'redirect_uri': config['redirect_uri'],
            'scope': 'openid offline_access Files.ReadWrite.All',  # Agregar openid requerido
        }

        _logger.info('Intentando obtener token de OneDrive usando endpoint común')

        try:
            resp = requests.post(url, data=data, timeout=30)
            _logger.info('Respuesta de Microsoft: Status %s', resp.status_code)

            if resp.status_code != 200:
                response_data = {}
                try:
                    response_data = resp.json()
                except:
                    pass

                error_description = response_data.get('error_description', resp.text)
                error_code = response_data.get('error', 'unknown_error')

                _logger.error('Error obteniendo token OneDrive: Status %s, Error: %s, Description: %s',
                             resp.status_code, error_code, error_description)

                if 'invalid_grant' in error_code or 'expired' in error_description.lower():
                    raise UserError(_('El refresh token ha expirado o es inválido. Necesitas reautorizar la aplicación.'))
                elif 'invalid_client' in error_code:
                    raise UserError(_('Las credenciales del cliente (client_id/client_secret) son incorrectas.'))
                elif 'unauthorized_client' in error_code:
                    raise UserError(_('El cliente no está autorizado para usar este grant type.'))
                else:
                    raise UserError(_('Error obteniendo token de OneDrive: %s - %s') % (error_code, error_description))

            token_data = resp.json()
            if not token_data.get('access_token'):
                _logger.error('Respuesta exitosa pero sin access_token: %s', token_data)
                raise UserError(_('La respuesta no contiene un token de acceso válido.'))

            _logger.info('Token de OneDrive obtenido exitosamente')
            return token_data.get('access_token')

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión obteniendo token OneDrive: %s', str(e))
            raise UserError(_('Error de conexión con Microsoft: %s') % str(e))

    def _detect_account_type(self, token):
        """
        Detecta si es una cuenta personal o empresarial de OneDrive
        """
        headers = {'Authorization': f'Bearer {token}'}

        try:
            # Intentar acceder al perfil del usuario para determinar el tipo de cuenta
            profile_url = 'https://graph.microsoft.com/v1.0/me'
            resp = requests.get(profile_url, headers=headers, timeout=10)

            if resp.status_code == 200:
                user_data = resp.json()
                # Si tiene 'businessPhones' y no está vacío, probablemente es cuenta empresarial
                # Si tiene 'userPrincipalName' con dominio corporativo, es empresarial
                user_principal = user_data.get('userPrincipalName', '')
                business_phones = user_data.get('businessPhones', [])

                # Verificar si es un dominio corporativo conocido vs personal (outlook.com, hotmail.com, live.com)
                personal_domains = ['outlook.com', 'hotmail.com', 'live.com', 'gmail.com']
                is_personal_domain = any(domain in user_principal.lower() for domain in personal_domains)

                if is_personal_domain:
                    _logger.info('Detectada cuenta personal de OneDrive: %s', user_principal)
                    return 'personal'
                else:
                    _logger.info('Detectada cuenta empresarial de OneDrive: %s', user_principal)
                    return 'business'

        except Exception as e:
            _logger.warning('No se pudo detectar el tipo de cuenta: %s', str(e))

        # Por defecto, asumir que es empresarial y luego manejar el error si no tiene licencia SPO
        return 'business'

    def _get_drive_endpoint(self, account_type, folder_id=None):
        """
        Obtiene el endpoint correcto según el tipo de cuenta
        """
        if account_type == 'personal':
            # Para cuentas personales, usar el endpoint estándar
            if folder_id:
                return f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
            else:
                return 'https://graph.microsoft.com/v1.0/me/drive/root/children'
        else:
            # Para cuentas empresariales, usar el mismo endpoint pero manejar errores de SPO
            if folder_id:
                return f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
            else:
                return 'https://graph.microsoft.com/v1.0/me/drive/root/children'

    def list_files(self, folder_id=None):
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}

        # Detectar tipo de cuenta automáticamente
        account_type = self._detect_account_type(token)
        _logger.info('Tipo de cuenta detectado: %s', account_type)

        # Obtener el endpoint correcto según el tipo de cuenta
        url = self._get_drive_endpoint(account_type, folder_id)

        try:
            resp = requests.get(url, headers=headers, timeout=30)

            # Si es exitoso, retornar los archivos
            if resp.status_code == 200:
                files = resp.json().get('value', [])
                _logger.info('Archivos obtenidos exitosamente desde %s: %d archivos', account_type, len(files))
                return files

            # Si falla, analizar el error
            response_data = {}
            try:
                response_data = resp.json()
            except:
                pass

            error_message = response_data.get('error', {}).get('message', '')
            error_code = response_data.get('error', {}).get('code', '')

            _logger.warning('Error %s al acceder a OneDrive %s: %s', resp.status_code, account_type, error_message)

            # Si es error de licencia SPO y detectamos cuenta empresarial, intentar como cuenta personal
            if ('SPO license' in error_message or 'Tenant does not have' in error_message or
                'BadRequest' in error_code) and account_type == 'business':

                _logger.info('Error de licencia SPO detectado. Intentando acceso como cuenta personal...')

                # Intentar con endpoint de cuenta personal
                personal_url = self._get_drive_endpoint('personal', folder_id)
                resp = requests.get(personal_url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    files = resp.json().get('value', [])
                    _logger.info('Archivos obtenidos exitosamente desde cuenta personal: %d archivos', len(files))
                    return files
                else:
                    _logger.error('Error también con cuenta personal: %s', resp.text)
                    raise UserError(_('No se pudieron listar los archivos de OneDrive. Error: %s') % resp.text)
            else:
                _logger.error('Error listando archivos OneDrive: %s', error_message)
                raise UserError(_('No se pudieron listar los archivos de OneDrive. Error: %s') % error_message)

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión listando archivos OneDrive: %s', str(e))
            raise UserError(_('Error de conexión con OneDrive: %s') % str(e))

    def download_file(self, onedrive_id):
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{onedrive_id}/content'
        resp = requests.get(url, headers=headers, stream=True)
        if resp.status_code != 200:
            _logger.error('Error descargando archivo OneDrive: %s', resp.text)
            raise UserError(_('No se pudo descargar el archivo de OneDrive.'))
        return resp.content

    def upload_file(self, folder_id, file_name, file_content):
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream',
        }
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{file_name}:/content'
        resp = requests.put(url, headers=headers, data=file_content)
        if resp.status_code not in (200, 201):
            _logger.error('Error subiendo archivo OneDrive: %s', resp.text)
            raise UserError(_('No se pudo subir el archivo a OneDrive.'))
        return resp.json()

    def sync_onedrive_files(self, folder_id=None):
        """
        Sincroniza los archivos de OneDrive con el modelo onedrive.document en Odoo.
        Si folder_id es None, sincroniza la raíz.
        """
        try:
            _logger.info('Iniciando sincronización de OneDrive. Folder ID: %s', folder_id or 'root')
            files = self.list_files(folder_id)
            _logger.info('Se encontraron %s elementos en OneDrive', len(files))

            # Debug: Mostrar información detallada de los primeros elementos
            for i, item in enumerate(files[:3]):  # Solo los primeros 3 para debug
                _logger.info('Elemento %d: name=%s, tiene_file=%s, tiene_folder=%s, keys=%s',
                           i+1, item.get('name'), bool(item.get('file')), bool(item.get('folder')), list(item.keys()))

            OneDriveDocument = self.env['onedrive.document']
            synced_count = 0
            updated_count = 0
            created_count = 0

            for file in files:
                # Cambiar la lógica de filtrado para ser más inclusiva
                is_file = file.get('file') is not None
                is_folder = file.get('folder') is not None

                _logger.info('Procesando elemento: %s, es_archivo=%s, es_carpeta=%s',
                           file.get('name'), is_file, is_folder)

                # Por ahora, procesar solo archivos (no carpetas)
                if not is_file:
                    _logger.debug('Omitiendo %s: %s', 'carpeta' if is_folder else 'elemento desconocido', file.get('name'))
                    continue

                try:
                    # Convertir fecha si existe
                    last_modified = None
                    if file.get('lastModifiedDateTime'):
                        try:
                            from datetime import datetime
                            # El formato típico es: 2023-12-01T10:30:00.000Z
                            date_str = file.get('lastModifiedDateTime').replace('Z', '+00:00')
                            last_modified = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        except Exception as date_error:
                            _logger.warning('Error parseando fecha %s: %s', file.get('lastModifiedDateTime'), date_error)

                    vals = {
                        'name': file.get('name'),
                        'onedrive_id': file.get('id'),
                        'file_url': file.get('@microsoft.graph.downloadUrl'),
                        'file_size': file.get('size', 0),
                        'file_type': file.get('file', {}).get('mimeType'),
                        'owner': file.get('createdBy', {}).get('user', {}).get('displayName'),
                        'last_modified': last_modified,
                        'is_folder': False,  # Marcar explícitamente como archivo
                    }

                    _logger.info('Datos del archivo %s: %s', file.get('name'), vals)

                    doc = OneDriveDocument.search([('onedrive_id', '=', file.get('id'))], limit=1)
                    if doc:
                        doc.write(vals)
                        updated_count += 1
                        _logger.info('Archivo actualizado: %s (ID: %s)', file.get('name'), doc.id)
                    else:
                        new_doc = OneDriveDocument.create(vals)
                        created_count += 1
                        _logger.info('Archivo creado: %s (ID: %s)', file.get('name'), new_doc.id)

                    synced_count += 1

                except Exception as e:
                    _logger.error('Error sincronizando archivo %s: %s', file.get('name'), str(e))
                    _logger.error('Datos del archivo problemático: %s', file)
                    continue

            _logger.info('Sincronización completada. Total: %s, Creados: %s, Actualizados: %s',
                        synced_count, created_count, updated_count)

            return {
                'success': True,
                'synced_count': synced_count,
                'created_count': created_count,
                'updated_count': updated_count,
                'message': _('Sincronización completada exitosamente. %s archivos procesados (%s creados, %s actualizados).') % (synced_count, created_count, updated_count)
            }

        except Exception as e:
            _logger.error('Error durante la sincronización de OneDrive: %s', str(e))
            return {
                'success': False,
                'error': str(e),
                'message': _('Error durante la sincronización: %s') % str(e)
            }

    def diagnose_connection(self):
        """
        Método para diagnosticar problemas de conexión con OneDrive
        """
        _logger.info('=== INICIO DIAGNÓSTICO ONEDRIVE ===')

        # 1. Verificar configuración
        config = self._get_config()
        settings = self.env['onedrive.settings'].search([], limit=1)

        _logger.info('Configuración cargada:')
        for key, value in config.items():
            if value:
                if key in ['client_secret', 'refresh_token']:
                    _logger.info('  %s: ****** (oculto, pero presente)', key)
                else:
                    _logger.info('  %s: %s', key, value)
            else:
                _logger.error('  %s: ¡FALTA!', key)

        # 2. Verificar conectividad
        try:
            import socket
            socket.create_connection(("login.microsoftonline.com", 443), timeout=10)
            _logger.info('Conectividad a Microsoft: OK')
        except Exception as e:
            _logger.error('Error de conectividad a Microsoft: %s', str(e))
            return {'success': False, 'error': f'Sin conectividad: {str(e)}'}

        # 3. Intentar obtener token con más detalles
        try:
            missing_params = [k for k, v in config.items() if not v]
            if missing_params:
                # Si falta solo el refresh_token, proporcionar URL de autorización
                if missing_params == ['refresh_token'] and settings:
                    auth_url = settings.get_auth_url()
                    if auth_url:
                        return {
                            'success': False,
                            'error': f'Falta refresh_token. Autoriza la aplicación en: {auth_url}',
                            'auth_url': auth_url
                        }

                return {
                    'success': False,
                    'error': f'Faltan parámetros: {", ".join(missing_params)}'
                }

            url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
            data = {
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'grant_type': 'refresh_token',
                'refresh_token': config['refresh_token'],
                'redirect_uri': config['redirect_uri'],
                'scope': 'openid offline_access Files.ReadWrite.All',  # Corregir para incluir openid
            }

            _logger.info('URL de token: %s', url)
            _logger.info('Datos enviados (sin secretos):')
            for key, value in data.items():
                if key in ['client_secret', 'refresh_token']:
                    _logger.info('  %s: ****** (presente)', key)
                else:
                    _logger.info('  %s: %s', key, value)

            resp = requests.post(url, data=data, timeout=30)
            _logger.info('Respuesta HTTP: %s', resp.status_code)
            _logger.info('Headers de respuesta: %s', dict(resp.headers))

            try:
                response_json = resp.json()
                if resp.status_code == 200:
                    _logger.info('Token obtenido exitosamente')
                    return {'success': True, 'message': 'Token obtenido correctamente'}
                else:
                    _logger.error('Error en respuesta JSON: %s', response_json)

                    # Manejo específico para invalid_grant
                    if response_json.get('error') == 'invalid_grant':
                        auth_url = settings.get_auth_url() if settings else None
                        if auth_url:
                            return {
                                'success': False,
                                'error': f'Refresh token inválido o expirado. Reautoriza en: {auth_url}',
                                'auth_url': auth_url
                            }
                        else:
                            return {
                                'success': False,
                                'error': 'Refresh token inválido o expirado. Necesitas reautorizar la aplicación.'
                            }

                    return {
                        'success': False,
                        'error': f"Error {resp.status_code}: {response_json.get('error', 'unknown')}",
                        'details': response_json
                    }
            except Exception as json_error:
                _logger.error('Error parseando respuesta JSON: %s', str(json_error))
                _logger.error('Respuesta raw: %s', resp.text)
                return {
                    'success': False,
                    'error': f'Respuesta inválida: {resp.text[:200]}'
                }

        except requests.exceptions.RequestException as e:
            _logger.error('Error de requests: %s', str(e))
            return {'success': False, 'error': f'Error de conexión: {str(e)}'}
        except Exception as e:
            _logger.error('Error inesperado: %s', str(e))
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}
        finally:
            _logger.info('=== FIN DIAGNÓSTICO ONEDRIVE ===')
