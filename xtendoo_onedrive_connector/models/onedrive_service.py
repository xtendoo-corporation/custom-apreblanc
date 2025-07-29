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

        # Agregar parámetros para obtener más elementos (por defecto Microsoft limita a pocos)
        if '?' in url:
            url += '&$top=1000'  # Solicitar hasta 1000 elementos por página
        else:
            url += '?$top=1000'

        try:
            all_files = []
            next_url = url

            # Manejar paginación para obtener todos los archivos
            while next_url:
                resp = requests.get(next_url, headers=headers, timeout=30)

                # Si es exitoso, procesar los archivos
                if resp.status_code == 200:
                    data = resp.json()
                    files = data.get('value', [])
                    all_files.extend(files)

                    # Verificar si hay más páginas
                    next_url = data.get('@odata.nextLink')
                    if next_url:
                        _logger.info('Obteniendo página siguiente: %d archivos más...', len(files))
                    else:
                        _logger.info('Archivos obtenidos exitosamente desde %s: %d archivos total', account_type, len(all_files))
                        break
                else:
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
                        if '?' in personal_url:
                            personal_url += '&$top=1000'
                        else:
                            personal_url += '?$top=1000'

                        resp = requests.get(personal_url, headers=headers, timeout=30)

                        if resp.status_code == 200:
                            data = resp.json()
                            files = data.get('value', [])
                            all_files.extend(files)
                            next_url = data.get('@odata.nextLink')
                            _logger.info('Archivos obtenidos exitosamente desde cuenta personal: %d archivos', len(files))
                        else:
                            _logger.error('Error también con cuenta personal: %s', resp.text)
                            raise UserError(_('No se pudieron listar los archivos de OneDrive. Error: %s') % resp.text)
                    else:
                        _logger.error('Error listando archivos OneDrive: %s', error_message)
                        raise UserError(_('No se pudieron listar los archivos de OneDrive. Error: %s') % error_message)

            return all_files

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

    def sync_onedrive_files(self, folder_id=None, recursive=True, parent_doc_id=None, max_depth=3, current_depth=0):
        """
        Sincroniza los archivos de OneDrive con el modelo onedrive.document en Odoo.
        Si folder_id es None, sincroniza la raíz.
        Si recursive es True, explora carpetas recursivamente.
        Si parent_doc_id se proporciona, asigna como padre a los elementos encontrados.
        max_depth controla la profundidad máxima de exploración (por defecto 3 niveles).
        current_depth es el nivel actual de profundidad.
        """
        try:
            _logger.info('Iniciando sincronización de OneDrive. Folder ID: %s, Recursivo: %s, Parent Doc ID: %s, Profundidad: %d/%d',
                        folder_id or 'root', recursive, parent_doc_id, current_depth, max_depth)

            # Verificar si hemos alcanzado la profundidad máxima
            if current_depth >= max_depth:
                _logger.warning('Profundidad máxima alcanzada (%d), deteniendo exploración recursiva', max_depth)
                return {
                    'success': True,
                    'synced_count': 0,
                    'created_count': 0,
                    'updated_count': 0,
                    'message': _('Profundidad máxima alcanzada')
                }

            files = self.list_files(folder_id)
            _logger.info('Se encontraron %s elementos en OneDrive (profundidad %d)', len(files), current_depth)

            # Debug: Mostrar información detallada de los primeros elementos
            for i, item in enumerate(files[:3]):  # Solo los primeros 3 para debug
                _logger.info('Elemento %d: name=%s, tiene_file=%s, tiene_folder=%s, keys=%s',
                           i+1, item.get('name'), bool(item.get('file')), bool(item.get('folder')), list(item.keys()))

            OneDriveDocument = self.env['onedrive.document']
            synced_count = 0
            updated_count = 0
            created_count = 0

            for item in files:
                # Detectar si es archivo o carpeta
                is_file = item.get('file') is not None
                is_folder = item.get('folder') is not None

                _logger.info('Procesando elemento: %s, es_archivo=%s, es_carpeta=%s (profundidad %d)',
                           item.get('name'), is_file, is_folder, current_depth)

                try:
                    # Procesar tanto archivos como carpetas
                    if is_file or is_folder:
                        # Convertir fecha si existe
                        last_modified = None
                        if item.get('lastModifiedDateTime'):
                            try:
                                from datetime import datetime
                                # El formato típico es: 2023-12-01T10:30:00.000Z
                                date_str = item.get('lastModifiedDateTime').replace('Z', '+00:00')
                                last_modified_with_tz = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                # Convertir a naive datetime (sin timezone) que es lo que espera Odoo
                                last_modified = last_modified_with_tz.replace(tzinfo=None)
                            except Exception as date_error:
                                _logger.warning('Error parseando fecha %s: %s', item.get('lastModifiedDateTime'), date_error)

                        vals = {
                            'name': item.get('name'),
                            'onedrive_id': item.get('id'),
                            'file_url': item.get('@microsoft.graph.downloadUrl') if is_file else item.get('webUrl'),
                            'file_size': item.get('size', 0),
                            'file_type': item.get('file', {}).get('mimeType') if is_file else 'folder',
                            'owner': item.get('createdBy', {}).get('user', {}).get('displayName'),
                            'last_modified': last_modified,
                            'is_folder': is_folder,
                            'parent_id': parent_doc_id,  # Asignar el parent_id si se proporciona
                        }

                        _logger.info('Datos del elemento %s (parent_id=%s, profundidad=%d): %s',
                                   item.get('name'), parent_doc_id, current_depth, vals)

                        doc = OneDriveDocument.search([('onedrive_id', '=', item.get('id'))], limit=1)
                        if doc:
                            doc.write(vals)
                            updated_count += 1
                            _logger.info('Elemento actualizado: %s (ID: %s, Parent ID: %s)', item.get('name'), doc.id, parent_doc_id)
                            current_doc_id = doc.id
                        else:
                            try:
                                new_doc = OneDriveDocument.create(vals)
                                # FORZAR COMMIT para asegurar que se guarda
                                self.env.cr.commit()
                                created_count += 1
                                _logger.info('Elemento creado y confirmado: %s (ID: %s, Parent ID: %s)', item.get('name'), new_doc.id, parent_doc_id)
                                current_doc_id = new_doc.id

                                # Verificar que realmente se creó
                                verification = OneDriveDocument.search([('id', '=', new_doc.id)], limit=1)
                                if not verification:
                                    _logger.error('❌ ERROR: El documento %s no se pudo verificar después de crear!', item.get('name'))
                                else:
                                    _logger.info('✅ VERIFICADO: Documento %s existe en BD con ID %s', item.get('name'), new_doc.id)

                                # REFRESCAR VISTA DESPUÉS DE CREAR
                                self.env['ir.actions.client'].with_context({'tag': 'reload'}).run()
                            except Exception as create_error:
                                _logger.error('❌ ERROR creando documento %s: %s', item.get('name'), str(create_error))
                                continue

                        synced_count += 1

                        # Si es carpeta, recursive=True y no hemos alcanzado la profundidad máxima, sincronizar contenido
                        if is_folder and recursive and current_depth < max_depth:
                            _logger.info('Explorando carpeta: %s (ID: %s, Doc ID: %s) - Profundidad %d/%d',
                                       item.get('name'), item.get('id'), current_doc_id, current_depth + 1, max_depth)
                            try:
                                # Pasar current_doc_id como parent_doc_id para los elementos hijos
                                # Incrementar current_depth para el siguiente nivel
                                folder_result = self.sync_onedrive_files(
                                    folder_id=item.get('id'),
                                    recursive=True,  # Mantener recursivo=True
                                    parent_doc_id=current_doc_id,
                                    max_depth=max_depth,
                                    current_depth=current_depth + 1
                                )
                                if folder_result['success']:
                                    synced_count += folder_result['synced_count']
                                    created_count += folder_result['created_count']
                                    updated_count += folder_result['updated_count']
                                    _logger.info('Carpeta %s procesada: +%d elementos hijos (profundidad %d)',
                                               item.get('name'), folder_result['synced_count'], current_depth + 1)
                                else:
                                    _logger.warning('Error procesando carpeta %s: %s', item.get('name'), folder_result.get('error'))
                            except Exception as folder_error:
                                _logger.error('Error explorando carpeta %s: %s', item.get('name'), str(folder_error))
                        elif is_folder and current_depth >= max_depth:
                            _logger.info('Carpeta %s omitida por profundidad máxima (%d/%d)',
                                       item.get('name'), current_depth, max_depth)
                    else:
                        _logger.debug('Omitiendo elemento desconocido: %s', item.get('name'))

                except Exception as e:
                    _logger.error('Error sincronizando elemento %s: %s', item.get('name'), str(e))
                    _logger.error('Datos del elemento problemático: %s', item)
                    continue

            _logger.info('Sincronización completada (profundidad %d). Total: %s, Creados: %s, Actualizados: %s',
                        current_depth, synced_count, created_count, updated_count)

            # REFRESCAR VISTA DESPUÉS DE COMPLETAR TODA LA SINCRONIZACIÓN
            if current_depth == 0:  # Solo refrescar al finalizar la sincronización completa
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }

            return {
                'success': True,
                'synced_count': synced_count,
                'created_count': created_count,
                'updated_count': updated_count,
                'message': _('Sincronización completada exitosamente. %s elementos procesados (%s creados, %s actualizados).') % (synced_count, created_count, updated_count)
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
