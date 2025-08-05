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
                'sync_folder': None,
            }

        return {
            'client_id': settings.onedrive_client_id,
            'client_secret': settings.onedrive_client_secret,
            'tenant_id': settings.onedrive_tenant_id,
            'redirect_uri': settings.onedrive_redirect_uri,
            'refresh_token': settings.onedrive_refresh_token,
            'sync_folder': settings.onedrive_sync_folder,
        }

    def _get_token(self):
        """Obtener el tokeen de acceso para la API de OneDrive"""
        config = self._get_config()

        if not config['tenant_id']:
            raise UserError(_('El Tenant ID no está configurado correctamente. Por favor, verifica la configuración en Odoo.'))

        if not config['client_id'] or not config['client_secret']:
            raise UserError(_('Cliente ID o Cliente Secret no configurados correctamente. Por favor, verifica la configuración en Odoo.'))

        # Determinar el tipo de grant a usar
        # Si tenemos refresh_token, usamos flujo delegado (usuario específico)
        # Si no, usamos client_credentials (aplicación)
        if config['refresh_token']:
            _logger.info('Usando flujo de autenticación delegada (refresh_token)')
            token_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }

            data = {
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'grant_type': 'refresh_token',
                'refresh_token': config['refresh_token'],
                'redirect_uri': config['redirect_uri'],
                # Para autenticación delegada, usar scopes específicos sin .default
                'scope': 'offline_access Files.ReadWrite.All',
            }

            grant_type = 'delegated'
        else:
            _logger.info('Usando flujo de autenticación de aplicación (client_credentials)')
            token_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }

            data = {
                'client_id': config['client_id'],
                # Para autenticación de aplicación, usar solo .default
                'scope': 'https://graph.microsoft.com/.default',
                'client_secret': config['client_secret'],
                'grant_type': 'client_credentials',
            }

            grant_type = 'application'

        response = requests.post(token_url, headers=headers, data=data)

        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get('access_token')
            # Guardar también el tipo de autenticación en la sesión para usarlo después
            self.env.context = dict(self.env.context, onedrive_auth_type=grant_type)
            _logger.info('Token obtenido exitosamente (tipo: %s): %s', grant_type, token)
            return token
        else:
            _logger.error('Error obteniendo token de OneDrive: %s - %s', response.status_code, response.text)
            raise UserError(_('Error obteniendo token de OneDrive: %s - %s') % (response.status_code, response.text))

    def verify_token(self, token):
        """Verificar el token obtenido"""
        headers = {'Authorization': f'Bearer {token}'}
        verify_url = 'https://graph.microsoft.com/v1.0/me/'

        response = requests.get(verify_url, headers=headers)

        if response.status_code == 200:
            _logger.info('Verificación de token exitosa. Usuario: %s', response.json().get('userPrincipalName'))
            return True
        else:
            _logger.warning('Error en la verificación del token: %s - %s', response.status_code, response.text)
            raise UserError(_('Error en la verificación del token: %s - %s') % (response.status_code, response.text))

    def _detect_account_type(self, token):
        """
        Detecta si es una cuenta personal o empresarial de OneDrive
        """
        headers = {'Authorization': f'Bearer {token}'}

        # Determinar si estamos usando autenticación de app o delegada
        auth_type = self.env.context.get('onedrive_auth_type', 'application')
        _logger.info('Detectando tipo de cuenta con autenticación: %s', auth_type)

        # Si es autenticación delegada, podemos usar /me
        if auth_type == 'delegated':
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
                else:
                    _logger.warning('Error detectando tipo de cuenta con /me: %s - %s',
                                  resp.status_code, resp.text)
            except Exception as e:
                _logger.warning('Error detectando tipo de cuenta con /me: %s', str(e))
        else:
            # Si es autenticación de aplicación, intentamos determinar por el sitio raíz
            try:
                # Intentar acceder al sitio raíz para determinar si tiene SharePoint
                site_url = 'https://graph.microsoft.com/v1.0/sites/root'
                resp = requests.get(site_url, headers=headers, timeout=10)

                if resp.status_code == 200:
                    _logger.info('Detectada cuenta empresarial (con sitio SharePoint)')
                    return 'business'
                else:
                    _logger.warning('No se pudo acceder al sitio raíz: %s - %s',
                                  resp.status_code, resp.text)
            except Exception as e:
                _logger.warning('Error detectando tipo de cuenta con /sites/root: %s', str(e))

        # Por defecto, intentaremos con business primero y si falla cambiaremos a personal
        _logger.info('No se pudo detectar el tipo de cuenta. Usando business por defecto')
        return 'business'

    def _get_drive_endpoint(self, account_type, folder_id=None):
        """
        Obtiene el endpoint correcto según el tipo de cuenta y tipo de autenticación
        """
        # Determinar si estamos usando autenticación de app o delegada
        auth_type = self.env.context.get('onedrive_auth_type', 'application')
        _logger.info('Usando endpoint para autenticación tipo: %s', auth_type)

        # Para autenticación delegada, podemos usar /me
        if auth_type == 'delegated':
            if account_type == 'personal':
                # Para cuentas personales con auth delegada
                if folder_id:
                    return f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
                else:
                    return 'https://graph.microsoft.com/v1.0/me/drive/root/children'
            else:
                # Para cuentas empresariales con auth delegada
                if folder_id:
                    return f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
                else:
                    return 'https://graph.microsoft.com/v1.0/me/drive/root/children'
        else:
            # Para autenticación de aplicación, no podemos usar /me
            # Necesitamos usar /users/{userId} o /sites/{siteId}
            # Intentaremos con el primer sitio SharePoint que encontremos
            return f'https://graph.microsoft.com/v1.0/sites/root/drive/root/children'

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

    def download_file(self, onedrive_id, document_id=None):
        """
        Descarga un archivo de OneDrive y registra la acción en el chatter de las órdenes de venta relacionadas
        """
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{onedrive_id}/content'
        resp = requests.get(url, headers=headers, stream=True)
        if resp.status_code != 200:
            _logger.error('Error descargando archivo OneDrive: %s', resp.text)
            raise UserError(_('No se pudo descargar el archivo de OneDrive.'))

        # Registrar la descarga en el chatter de las órdenes de venta relacionadas
        try:
            # Buscar el documento por onedrive_id si no se proporciona document_id
            if document_id:
                document = self.env['onedrive.document'].browse(document_id)
            else:
                document = self.env['onedrive.document'].search([('onedrive_id', '=', onedrive_id)], limit=1)

            if document and document.exists():
                # Buscar todas las órdenes de venta relacionadas con este documento
                sale_orders = self.env['sale.order'].search([('onedrive_document_ids', 'in', document.id)])

                if sale_orders:
                    for sale_order in sale_orders:
                        sale_order.message_post(
                            body=f"El documento '{document.name}' fue descargado por {self.env.user.name}.",
                            subtype_xmlid='mail.mt_note'
                        )
                        _logger.info('Descarga registrada en chatter de orden de venta %s para documento: %s por usuario: %s',
                                   sale_order.name, document.name, self.env.user.name)
                else:
                    _logger.warning('No se encontraron órdenes de venta relacionadas con el documento %s (onedrive_id: %s)',
                                  document.name, onedrive_id)
            else:
                _logger.warning('No se encontró el documento con onedrive_id: %s para registrar descarga', onedrive_id)
        except Exception as e:
            _logger.error('Error registrando descarga en chatter: %s', str(e))
            # No interrumpir la descarga por un error en el chatter

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
        Si folder_id es None, sincroniza la raíz o la carpeta configurada en ajustes.
        Si recursive es True, explora carpetas recursivamente.
        Si parent_doc_id se proporciona, asigna como padre a los elementos encontrados.
        max_depth controla la profundidad máxima de exploración (por defecto 3 niveles).
        current_depth es el nivel actual de profundidad.
        """
        try:
            # Verificar la configuración explícitamente antes de obtener el token
            config = self._get_config()
            _logger.info('Configuración para sincronización: tenant_id=%s, client_id=%s',
                        config['tenant_id'] or 'NO CONFIGURADO',
                        config['client_id'] or 'NO CONFIGURADO')

            if not config['tenant_id']:
                return {
                    'success': False,
                    'error': 'El Tenant ID no está configurado correctamente',
                    'message': _('El Tenant ID no está configurado correctamente. Por favor, verifica la configuración en Odoo.')
                }

            # Si no se proporciona un folder_id pero hay una carpeta configurada, usarla
            if folder_id is None and current_depth == 0 and config['sync_folder']:
                _logger.info('Usando carpeta configurada para sincronización: %s', config['sync_folder'])
                folder_id = config['sync_folder']

            token = self._get_token()
            _logger.info('Token obtenido correctamente para la sincronización: %s', token)

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
            return {'success': False, 'error': 'Conexión fallida', 'title': 'Operación no válida'}

        # 3. Intentar obtener token con más detalles
        try:
            missing_params = [k for k, v in config.items() if not v and k != 'sync_folder']
            if missing_params:
                # Si falta solo el refresh_token, proporcionar URL de autorización
                if missing_params == ['refresh_token'] and settings:
                    auth_url = settings.get_auth_url()
                    if auth_url:
                        return {
                            'success': False,
                            'error': f'Conexión fallida. Autoriza la aplicación en: {auth_url}',
                            'auth_url': auth_url,
                            'title': 'Operación no válida'
                        }

                return {
                    'success': False,
                    'error': f'Conexión fallida. Faltan parámetros: {", ".join(missing_params)}',
                    'title': 'Operación no válida'
                }

            url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
            data = {
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'grant_type': 'refresh_token',
                'refresh_token': config['refresh_token'],
                'redirect_uri': config['redirect_uri'],
                'scope': 'openid offline_access Files.ReadWrite.All',
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

            try:
                response_json = resp.json()
                if resp.status_code == 200:
                    token = response_json.get('access_token')
                    _logger.info('Token obtenido exitosamente')

                    # 4. Verificar y crear carpeta de sincronización si está configurada
                    if config['sync_folder']:
                        _logger.info('Verificando existencia de la carpeta de sincronización: %s', config['sync_folder'])

                        # Determinar si es un ID o nombre/ruta
                        folder_path = config['sync_folder']
                        is_path = '/' in folder_path or '\\' in folder_path or not folder_path.startswith('0')

                        headers = {
                            'Authorization': f'Bearer {token}',
                            'Content-Type': 'application/json'
                        }

                        if is_path:
                            # Es un nombre de carpeta o ruta
                            folder_name = folder_path.replace('\\', '/').strip('/').split('/')[0]

                            # Listar carpetas en la raíz para ver si existe
                            list_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=folder ne null'
                            list_resp = requests.get(list_url, headers=headers, timeout=30)

                            if list_resp.status_code != 200:
                                _logger.error('Error listando carpetas de OneDrive: %s', list_resp.text)
                                return {'success': False, 'error': f'Error al listar carpetas: {list_resp.text[:100]}'}

                            root_folders = list_resp.json().get('value', [])
                            folder_exists = False
                            folder_id = None

                            # Verificar si la carpeta existe
                            for folder in root_folders:
                                if folder.get('name').lower() == folder_name.lower():
                                    folder_exists = True
                                    folder_id = folder.get('id')
                                    _logger.info('Carpeta encontrada: %s (ID: %s)', folder_name, folder_id)
                                    break

                            if not folder_exists:
                                # Crear la carpeta si no existe
                                _logger.info('Carpeta "%s" no encontrada. Procediendo a crearla...', folder_name)

                                create_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
                                create_data = {
                                    "name": folder_name,
                                    "folder": {},
                                    "@microsoft.graph.conflictBehavior": "rename"
                                }

                                create_resp = requests.post(
                                    create_url,
                                    headers=headers,
                                    json=create_data,
                                    timeout=30
                                )

                                if create_resp.status_code in (200, 201):
                                    created_folder = create_resp.json()
                                    _logger.info('✅ Carpeta creada exitosamente: %s (ID: %s)',
                                              created_folder.get('name'),
                                              created_folder.get('id'))

                                    # Actualizar la configuración con el ID de la carpeta creada
                                    if settings:
                                        settings.onedrive_sync_folder = created_folder.get('id')
                                        self.env.cr.commit()
                                        _logger.info('ID de carpeta actualizado en la configuración: %s', created_folder.get('id'))

                                    return {
                                        'success': True,
                                        'message': 'Conexión exitosa',
                                        'title': 'Operación válida'
                                    }
                                else:
                                    _logger.error('❌ Error creando carpeta en OneDrive: %s', create_resp.text)
                                    return {
                                        'success': False,
                                        'error': 'Conexión fallida',
                                        'title': 'Operación no válida'
                                    }
                            else:
                                return {
                                    'success': True,
                                    'message': 'Conexión exitosa',
                                    'title': 'Operación válida'
                                }
                        else:
                            # Es un ID, verificar que exista
                            item_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_path}'
                            item_resp = requests.get(item_url, headers=headers, timeout=30)

                            if item_resp.status_code == 200:
                                folder_info = item_resp.json()
                                _logger.info('Carpeta con ID %s encontrada: %s', folder_path, folder_info.get('name'))
                                return {
                                    'success': True,
                                    'message': 'Conexión exitosa',
                                    'title': 'Operación válida'
                                }
                            else:
                                # El ID no existe, crear una nueva carpeta
                                _logger.warning('No se encontró la carpeta con ID %s. Creando nueva carpeta...', folder_path)

                                # Crear una nueva carpeta con nombre "Odoo"
                                create_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
                                create_data = {
                                    "name": "Odoo",
                                    "folder": {},
                                    "@microsoft.graph.conflictBehavior": "rename"
                                }

                                create_resp = requests.post(
                                    create_url,
                                    headers=headers,
                                    json=create_data,
                                    timeout=30
                                )

                                if create_resp.status_code in (200, 201):
                                    created_folder = create_resp.json()
                                    _logger.info('✅ Carpeta Odoo creada exitosamente (ID: %s)',
                                              created_folder.get('id'))

                                    # Actualizar la configuración con el nuevo ID
                                    if settings:
                                        settings.onedrive_sync_folder = created_folder.get('id')
                                        self.env.cr.commit()

                                    return {
                                        'success': True,
                                        'message': 'Conexión exitosa',
                                        'title': 'Operación válida'
                                    }
                                else:
                                    _logger.error('❌ Error creando carpeta en OneDrive: %s', create_resp.text)
                                    return {
                                        'success': False,
                                        'error': 'Conexión fallida',
                                        'title': 'Operación no válida'
                                    }

                    # Si no hay carpeta configurada
                    return {'success': True, 'message': 'Conexión exitosa con OneDrive.'}
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
