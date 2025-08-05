from odoo import models, fields, api
import requests

class OneDriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'OneDrive Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string='Name', required=True)
    onedrive_id = fields.Char(string='OneDrive ID')
    file_url = fields.Char(string='File URL')
    preview_url = fields.Char(string='Preview URL', compute='_compute_preview_url')
    file_size = fields.Integer(string='File Size')
    file_type = fields.Char(string='File Type')
    owner = fields.Char(string='Owner')
    last_modified = fields.Datetime(string='Last Modified')
    parent_id = fields.Many2one('onedrive.document', string='Parent Folder')
    is_folder = fields.Boolean(string='Is Folder', default=False)
    file_data = fields.Binary(string='File Data')
    pdf_thumbnail = fields.Binary(string='PDF Thumbnail', compute='_compute_pdf_thumbnail', store=True)
    pdf_preview_url = fields.Char(string='PDF Preview URL', compute='_compute_pdf_preview_url')
    preview_data = fields.Binary(string='Preview Data', compute='_compute_preview_data', store=False)
    upload_file = fields.Binary(string='Upload File')
    upload_filename = fields.Char(string='Upload Filename')

    @api.onchange('file_data')
    def _onchange_file_data(self):
        """Actualizar automáticamente el nombre cuando se selecciona un archivo"""
        if self.file_data and not self.name:
            # El nombre del archivo se puede obtener desde varios lugares
            filename = None

            # 1. Desde el contexto si está disponible
            if self.env.context.get('filename'):
                filename = self.env.context.get('filename')

            # 2. Si no hay contexto, generar un nombre basado en timestamp
            if not filename:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'documento_{timestamp}'

            # Limpiar el nombre del archivo de caracteres no válidos
            import re
            clean_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            # Asignar el nombre limpio
            self.name = clean_filename

    @api.model
    def action_sync_onedrive(self):
        """
        Método llamado desde la interfaz para sincronizar con OneDrive
        """
        try:
            # Usar el servicio mejoradoo de OneDrive
            service = self.env['onedrive.service']
            result = service.sync()

            # Recargar la vista sin mostrar notificación
            if result['success']:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def action_download_file(self):
        """Descargar archivo directamente desde OneDrive usando la URL almacenada y registrar en el chatter"""
        if not self.file_url or self.is_folder:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No se puede descargar: archivo no válido o es una carpeta.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Intentar detectar si la descarga es desde una venta
        sale_order = None
        try:
            # Intentar obtener el ID de venta del contexto o de la URL
            sale_id = None

            # Verificar en el contexto
            params = self.env.context.get('params', {})
            if params.get('model') == 'sale.order' and params.get('id'):
                sale_id = params.get('id')

            # Si se encontró ID, buscar la venta
            if sale_id:
                sale_order = self.env['sale.order'].browse(sale_id).exists()
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error al detectar venta asociada: {e}")

        # Registrar la actividad en el chatter del documento OneDrive
        message = f"El documento '{self.name}' fue descargado por {self.env.user.name}."
        self.message_post(
            body=message,
            subtype_xmlid='mail.mt_note'
        )

        # Si se detectó una venta, también registrar en su chatter
        if sale_order:
            try:
                sale_order.message_post(
                    body=f"El documento de OneDrive '{self.name}' fue descargado por {self.env.user.name}.",
                    subtype_xmlid='mail.mt_note'
                )
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error(f"Error al registrar en el chatter de la venta: {e}")

        # Usar directamente la URL de OneDrive que ya funciona en el navegador
        return {
            'type': 'ir.actions.act_url',
            'url': self.file_url,
            'target': 'self',
        }

    def action_upload_file(self):
        """Subir archivo a OneDrive con estructura de carpetas específica"""
        # Oobtener el nombre de la carpeta raíz desde la configuración de OneDrive
        settings = self.env['onedrive.settings'].search([], limit=1)
        ROOT_FOLDER_NAME = settings.onedrive_sync_folder_name or "odoo"

        if not self.upload_file or not self.upload_filename:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Por favor, selecciona un archivo para subir.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            # Obtener el servicio de OneDrive
            onedrive_service = self.env['onedrive.service']
            access_token = onedrive_service._get_token()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }

            # Obtener el nombre de la venta ANTES de crear/buscar carpetas
            sale_name = self._get_sale_name()
            if not sale_name:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se pudo determinar el nombre de la venta.',
                        'type': 'warning',
                        'sticky': True,
                    }
                }

            # Paso 1: Verificar/crear carpeta raíz "odoo"
            root_folder_id = self._ensure_folder_exists(ROOT_FOLDER_NAME, None, headers)
            if not root_folder_id:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'No se pudo crear o encontrar la carpeta "{ROOT_FOLDER_NAME}".',
                        'type': 'danger',
                        'sticky': True,
                    }
                }

            # Paso 2: Verificar/crear carpeta de la venta con el nombre correcto desde el inicio
            sale_folder_id = self._ensure_folder_exists(sale_name, root_folder_id, headers)
            if not sale_folder_id:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'No se pudo crear o encontrar la carpeta "{sale_name}".',
                        'type': 'danger',
                        'sticky': True,
                    }
                }

            # Paso 3: Subir el archivo a la carpeta de la venta
            file_data = self._upload_file_to_folder(sale_folder_id, headers)
            if not file_data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se pudo subir el archivo a OneDrive.',
                        'type': 'danger',
                        'sticky': True,
                    }
                }

            # Paso 4: Actualizar los datos en Odoo
            self._update_document_data(file_data)

            # Cerrar formulario y mostrar notificación de éxito
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '¡Archivo subido exitosamente!',
                    'message': f'El archivo "{self.upload_filename}" se ha subido correctamente a OneDrive en la carpeta {ROOT_FOLDER_NAME}/{sale_name}/',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error al subir archivo',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _rename_folder_if_needed(self, folder_id, desired_name, headers):
        """Renombrar una carpeta en OneDrive si su nombre no coincide con el deseado"""
        try:
            # Obtener información de la carpeta actual
            folder_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}'
            response = requests.get(folder_url, headers=headers, timeout=30)

            if response.status_code == 200:
                folder_data = response.json()
                current_name = folder_data.get('name', '')

                # Renombrar solo si el nombre actual no coincide con el deseado
                if current_name != desired_name:
                    rename_data = {"name": desired_name}
                    rename_response = requests.patch(folder_url, headers=headers, json=rename_data, timeout=30)

                    if rename_response.status_code not in [200, 204]:
                        raise Exception(f"Error renombrando carpeta: {rename_response.status_code} - {rename_response.text}")

            else:
                raise Exception(f"Error obteniendo información de la carpeta: {response.status_code} - {response.text}")

        except Exception as e:
            raise Exception(f"Error en _rename_folder_if_needed: {str(e)}")

    def _get_sale_name(self):
        """Obtener el nombre de la venta actual - CON JAVASCRIPT BROWSER CAPTURE"""
        import logging
        _logger = logging.getLogger(__name__)

        _logger.info("=== INICIANDO _get_sale_name - JAVASCRIPT CAPTURE ===")

        # PRIORIDAD 0: CAAPTURAR DESDE JAVASCRIPT DEL NAVEGADOR
        try:
            # Intentar obtener el ID que el JavaScript capturó desde el navegador
            request_obj = None

            # Obtener request
            import odoo.http
            if hasattr(odoo.http, 'request') and odoo.http.request:
                request_obj = odoo.http.request
            elif self.env.context.get('request'):
                request_obj = self.env.context.get('request')

            if request_obj and hasattr(request_obj, 'httprequest'):
                # Buscar en headers o cookies si el JavaScript almacenó el ID
                headers = getattr(request_obj.httprequest, 'headers', {})
                cookies = getattr(request_obj.httprequest, 'cookies', {})

                # El JavaScript puede haber almacenado el ID en una cookie o header
                js_sale_id = None

                # Buscar en cookies primero
                if 'odoo_current_sale_id' in cookies:
                    try:
                        js_sale_id = int(cookies['odoo_current_sale_id'])
                        _logger.info(f"🍪 ID capturado desde cookie JavaScript: {js_sale_id}")
                    except (ValueError, TypeError):
                        pass

                # Si no está en cookies, buscar en headers personalizados
                if not js_sale_id:
                    for header_name, header_value in headers.items():
                        if 'sale' in header_name.lower() and 'id' in header_name.lower():
                            try:
                                js_sale_id = int(header_value)
                                _logger.info(f"📡 ID capturado desde header {header_name}: {js_sale_id}")
                                break
                            except (ValueError, TypeError):
                                continue

                # Verificar el ID capturado
                if js_sale_id:
                    with self.env.registry.cursor() as new_cr:
                        new_env = self.env(cr=new_cr)
                        sale_order = new_env['sale.order'].browse(js_sale_id)
                        if sale_order.exists():
                            _logger.info(f"✅ PRIORIDAD 0 - Sale order desde JAVASCRIPT: {sale_order.name}")
                            return sale_order.name
                        else:
                            _logger.warning(f"⚠️ ID {js_sale_id} desde JavaScript no existe en BD")

        except Exception as e:
            _logger.error(f"❌ Error capturando desde JavaScript: {e}")

        # PRIORIDAD 1: ANÁLISIS ULTRA-AGRESIVO DEL REQUEST (método anterior mejorado)
        try:
            params = self.env.context.get('params', {})
            _logger.info(f"Params del contexto: {params}")

            if params.get('model') == 'sale.order' and params.get('id'):
                context_sale_id = params.get('id')

                # Verificar si este ID es realmente actual buscando ventas modificadas recientemente
                from datetime import datetime, timedelta
                recent_threshold = datetime.now() - timedelta(minutes=10)

                # Buscar ventas modificadas en los últimos 10 minutos
                recent_sales = self.env['sale.order'].search([
                    ('write_date', '>=', recent_threshold.strftime('%Y-%m-%d %H:%M:%S'))
                ], order='write_date desc', limit=20)

                recent_ids = [s.id for s in recent_sales]
                _logger.info(f"IDs de ventas recientes (últimos 10 min): {recent_ids}")

                # Si el ID del contexto NO está en las ventas recientes, es probablemente obsoleto
                if context_sale_id not in recent_ids and recent_sales:
                    _logger.warning(f"🚨 CONTEXTO OBSOLETO DETECTADO: ID {context_sale_id} no está en ventas recientes")

                    # Usar la venta más reciente en su lugar
                    most_recent_sale = recent_sales[0]
                    _logger.warning(f"🔄 CORRECCIÓN AUTOMÁTICA: Usando venta más reciente {most_recent_sale.name} (ID: {most_recent_sale.id})")
                    return most_recent_sale.name

                # Si el ID está en las ventas recientes, verificar que realmente existe
                with self.env.registry.cursor() as new_cr:
                    new_env = self.env(cr=new_cr)
                    sale_order = new_env['sale.order'].browse(context_sale_id)
                    if sale_order.exists():
                        _logger.info(f"✅ PRIORIDAD 1 - Sale order válido desde contexto: {sale_order.name}")
                        return sale_order.name
                    else:
                        _logger.warning(f"⚠️ ID {context_sale_id} del contexto no existe")

        except Exception as e:
            _logger.error(f"❌ Error en análisis temporal: {e}")

        # PRIORIDAD 2: FALLBACK a venta más reciente del usuario
        try:
            _logger.warning("🆘 FALLBACK: Usando venta más reciente del usuario actual")

            user_id = self.env.uid
            recent_sales = self.env['sale.order'].search([
                '|',
                ('create_uid', '=', user_id),
                ('write_uid', '=', user_id)
            ], order='write_date desc', limit=5)

            if recent_sales:
                fallback_sale = recent_sales[0]
                _logger.warning(f"⚠️ FALLBACK - Usando: {fallback_sale.name}")
                return fallback_sale.name

        except Exception as e:
            _logger.error(f"❌ Error en fallback: {e}")

        # ÚLTIMO RECURSO
        _logger.error("❌ NO SE PUDO DETERMINAR LA VENTA ACTUAL")
        raise Exception(
            "No se pudo determinar la venta actual. El contexto parece estar corrupto. "
            "Por favor, RECARGA LA PÁGINA (F5) e intenta nuevamente."
        )

    def _calculate_confidence(self, source_name, pattern):
        """Calcular nivel de confianza para un ID encontrado"""
        confidence = 0

        # Bonificaciones por fuente
        source_bonuses = {
            'referrer': 10,
            'header_referer': 10,
            'current_url': 8,
            'json_params': 7,
            'args_id': 6,
            'form_id': 5,
        }
        confidence += source_bonuses.get(source_name, 0)

        # Bonificaciones por patrón (más específico = más confianza)
        if 'model=sale.order' in pattern:
            confidence += 10
        if 'res_model=sale.order' in pattern:
            confidence += 8
        if '/web#' in pattern:
            confidence += 5

        return confidence

    def _ensure_folder_exists(self, folder_name, parent_folder_id, headers):
        """Verificar si existe una carpeta, si no existe la crea - CORREGIDO PARA USAR VENTA ACTUAL"""
        import logging
        _logger = logging.getLogger(__name__)

        try:
            _logger.info(f"=== Buscando/creando carpeta: '{folder_name}' ===")

            # Construir URL para buscar carpetas
            if parent_folder_id:
                search_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{parent_folder_id}/children'
                _logger.info(f"Buscando en carpeta padre ID: {parent_folder_id}")
            else:
                search_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
                _logger.info("Buscando en carpeta raíz")

            # Limpiar el nombre de carpeta de caracteres problemáticos para OneDrive
            safe_folder_name = self._sanitize_folder_name(folder_name)
            _logger.info(f"Nombre original: '{folder_name}' -> Nombre seguro: '{safe_folder_name}'")

            # Obtener TODAS las carpetas para buscar la correcta
            _logger.info(f"Obteniendo lista de carpetas desde: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                all_items = data.get('value', [])
                _logger.info(f"Total de items encontrados: {len(all_items)}")

                # Filtrar solo carpetas
                folders = [item for item in all_items if item.get('folder') is not None]
                _logger.info(f"Carpetas encontradas: {len(folders)}")

                # Buscar carpeta con nombre exacto
                for folder in folders:
                    folder_name_found = folder.get('name', '')
                    _logger.info(f"Comparando: '{safe_folder_name}' == '{folder_name_found}'")
                    if folder_name_found == safe_folder_name:
                        folder_id = folder['id']
                        _logger.info(f"✅ Carpeta encontrada: '{folder_name_found}' con ID: {folder_id}")
                        return folder_id

                _logger.info(f"❌ No se encontró carpeta '{safe_folder_name}' - se creará nueva")
            else:
                _logger.error(f"Error obteniendo lista de carpetas: {response.status_code} - {response.text}")

            # La carpeta no existe, crearla
            _logger.info(f"Creando nueva carpeta: '{safe_folder_name}'")
            create_data = {
                "name": safe_folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename"  # Renombrar automáticamente si hay conflicto
            }

            create_response = requests.post(search_url, headers=headers, json=create_data, timeout=30)
            _logger.info(f"Respuesta de creación: {create_response.status_code}")

            if create_response.status_code == 201:
                folder_id = create_response.json()['id']
                created_name = create_response.json().get('name', safe_folder_name)
                _logger.info(f"✅ Carpeta creada exitosamente: '{created_name}' con ID: {folder_id}")
                return folder_id
            else:
                raise Exception(f"Error creando carpeta {safe_folder_name}: {create_response.status_code} - {create_response.text}")

        except Exception as e:
            _logger.error(f"❌ Error en _ensure_folder_exists para {folder_name}: {str(e)}")
            raise Exception(f"Error en _ensure_folder_exists para {folder_name}: {str(e)}")

    def _sanitize_folder_name(self, folder_name):
        """Limpiar el nombre de carpeta para OneDrive"""
        import re

        # Caracteres no permitidos en OneDrive: \ / : * ? " < > |
        # También espacios al inicio/final y algunos caracteres especiales
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)

        # Remover espacios al inicio y final
        safe_name = safe_name.strip()

        # Remover puntos al final (OneDrive no los permite)
        safe_name = safe_name.rstrip('.')

        # Si queda vacío, usar un nombre por defecto
        if not safe_name:
            safe_name = "DOCUMENTO"

        return safe_name

    def _upload_file_to_folder(self, folder_id, headers):
        """Subir archivo a una carpeta específica de OneDrive"""
        try:
            import base64

            # Decodificar el archivo
            file_content = base64.b64decode(self.upload_file)

            # URL para subir archivo
            upload_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{self.upload_filename}:/content'

            # Headers para subir archivo binario
            upload_headers = {
                'Authorization': headers['Authorization'],
                'Content-Type': 'application/octet-stream',
            }

            # Subir archivo
            response = requests.put(upload_url, headers=upload_headers, data=file_content, timeout=60)

            if response.status_code in [200, 201]:
                return response.json()
            else:
                raise Exception(f"Error subiendo archivo: {response.status_code} - {response.text}")

        except Exception as e:
            raise Exception(f"Error en _upload_file_to_folder: {str(e)}")

    def _update_document_data(self, file_data):
        """Actualizar los datos del documento en Odoo con la información de OneDrive"""
        try:
            # Obtener URL de descarga
            download_url = file_data.get('@microsoft.graph.downloadUrl', '')

            # Convertir fecha de OneDrive al formato que espera Odoo
            last_modified = None
            if file_data.get('lastModifiedDateTime'):
                try:
                    from datetime import datetime
                    # OneDrive devuelve fecha en formato ISO: '2025-07-28T09:17:20Z'
                    iso_date = file_data.get('lastModifiedDateTime')
                    # Remover la 'Z' del final si existe
                    if iso_date.endswith('Z'):
                        iso_date = iso_date[:-1]
                    # Convertir de ISO a datetime
                    dt_object = datetime.fromisoformat(iso_date)
                    # Convertir a string en formato que espera Odoo
                    last_modified = dt_object.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as date_error:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.warning("Error convirtiendo fecha %s: %s", file_data.get('lastModifiedDateTime'), str(date_error))
                    last_modified = None

            # Actualizar campos del documento
            update_data = {
                'name': file_data.get('name', self.upload_filename),
                'onedrive_id': file_data.get('id', ''),
                'file_url': download_url,
                'file_size': file_data.get('size', 0),
                'file_type': file_data.get('file', {}).get('mimeType', ''),
                'owner': file_data.get('createdBy', {}).get('user', {}).get('displayName', ''),
                'is_folder': False,
                'file_data': self.upload_file,  # Mantener una copia local
            }

            # Solo agregar last_modified si se pudo convertir correctamente
            if last_modified:
                update_data['last_modified'] = last_modified

            self.write(update_data)

            # Limpiar campos de upload
            self.upload_file = False
            self.upload_filename = False

        except Exception as e:
            raise Exception(f"Error actualizando datos en Odoo: {str(e)}")

    @api.depends('file_url')
    def _compute_preview_url(self):
        for record in self:
            if record.file_url and not record.is_folder:
                # Usar nuestro controlador proxy para la previsualización
                record.preview_url = f'/onedrive/preview/{record.id}'
            else:
                record.preview_url = False

    @api.depends('file_url', 'file_data')
    def _compute_preview_data(self):
        """Descargar archivo de OneDrive para previsualización si no está almacenado localmente"""
        for record in self:
            if record.file_data:
                # Si ya tenemos el archivo localmente, usarlo
                record.preview_data = record.file_data
            elif record.file_url and not record.is_folder:
                # Intentar descargar el archivo de OneDrive para previsualización
                try:
                    response = requests.get(record.file_url, timeout=30)
                    if response.status_code == 200:
                        import base64
                        record.preview_data = base64.b64encode(response.content)
                    else:
                        record.preview_data = False
                except Exception:
                    record.preview_data = False
            else:
                record.preview_data = False

    def action_load_preview(self):
        """Cargar archivo para previsualización y almacenarlo permanentemente"""
        for record in self:
            if record.file_url and not record.file_data and not record.is_folder:
                try:
                    import base64
                    # Agregar headers para evitar bloqueos de OneDrive
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    response = requests.get(record.file_url, timeout=30, headers=headers, stream=True)
                    if response.status_code == 200:
                        # Leer el contenido del archivo
                        file_content = response.content
                        # Codificar en base64 para almacenar en Odoo
                        record.file_data = base64.b64encode(file_content)

                        # Mostrar mensaje de éxito
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': '¡Archivo cargado!',
                                'message': f'El archivo "{record.name}" se ha cargado correctamente y ya se puede previsualizar.',
                                'type': 'success',
                                'sticky': False,
                            }
                        }
                    else:
                        # Mostrar error si no se puede descargar
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': 'Error al cargar archivo',
                                'message': f'No se pudo descargar el archivo desde OneDrive. Código de error: {response.status_code}',
                                'type': 'danger',
                                'sticky': True,
                            }
                        }
                except Exception as e:
                    # Mostrar error si hay excepción
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Error al cargar archivo',
                            'message': f'Error: {str(e)}',
                            'type': 'danger',
                            'sticky': True,
                        }
                    }
        return True

    def get_download_url(self):
        """Obtener URL de descarga a través de nuestro proxy"""
        return f'/onedrive/download/{self.id}'

    def get_direct_preview_url(self):
        """Obtener URL directa para casos específicos"""
        if not self.file_url or self.is_folder:
            return False

        # Para algunos tipos de archivo, intentar URLs de previsualización directa
        if 'sharepoint.com' in self.file_url or 'onedrive.live.com' in self.file_url:
            if '?download=1' in self.file_url:
                return self.file_url.replace('?download=1', '?embed=1')
            elif 'view.aspx' in self.file_url:
                return self.file_url + '&action=embedview'

        return self.file_url

    @api.depends('file_data', 'file_type')
    def _compute_pdf_preview_url(self):
        """Generar URL para previsualización de PDF"""
        for record in self:
            if record.file_data and record.file_type == 'pdf':
                record.pdf_preview_url = f'/onedrive/pdf/{record.id}'
            else:
                record.pdf_preview_url = False

    @api.depends('file_data', 'file_type')
    def _compute_pdf_thumbnail(self):
        """Generar thumbnail de la primera página del PDF"""
        for record in self:
            if record.file_data and record.file_type and 'pdf' in record.file_type:
                try:
                    import base64
                    import io
                    from pdf2image import convert_from_bytes
                    from PIL import Image

                    # Decodificar el PDF
                    pdf_content = base64.b64decode(record.file_data)

                    # Convertir primera página a imagen
                    images = convert_from_bytes(pdf_content, first_page=1, last_page=1, dpi=150)

                    if images:
                        # Redimensionar la imagen para que sea más pequeña
                        image = images[0]
                        image.thumbnail((800, 600), Image.Resampling.LANCZOS)

                        # Convertir a bytes y codificar en base64
                        img_buffer = io.BytesIO()
                        image.save(img_buffer, format='JPEG', quality=85)
                        img_buffer.seek(0)

                        record.pdf_thumbnail = base64.b64encode(img_buffer.getvalue())
                    else:
                        record.pdf_thumbnail = False

                except Exception as e:
                    # Si hay error en la conversión, no mostrar thumbnail
                    record.pdf_thumbnail = False
            else:
                record.pdf_thumbnail = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para subir automáticamente archivos a OneDrive"""
        records = super().create(vals_list)

        # Para cada registro creado, verificar si tiene archivo para subir
        for record in records:
            # Verificar si hay archivo para subir (puede venir en file_data o upload_file)
            has_file = False

            # Si viene en file_data y name, preparar para subida
            if record.file_data and record.name and not record.file_url:
                # Mover file_data a upload_file para procesarlo
                record.upload_file = record.file_data
                record.upload_filename = record.name
                has_file = True
            # O si viene directamente en upload_file
            elif record.upload_file and record.upload_filename:
                has_file = True

            if has_file:
                try:
                    # FORZAR ACTUALIZACIÓN DEL CONTEXTO antes de la subida
                    # Esto asegura que tenemos la información más reciente de la venta
                    record.env.invalidate_all()  # Limpiar cache de Odoo

                    # Intentar obtener el contexto fresco desde la request actual
                    current_request = record.env.context.get('request')
                    if current_request and hasattr(current_request, 'httprequest'):
                        # Obtener información fresca de la URL actual
                        url = getattr(current_request.httprequest, 'url', '')
                        referrer = getattr(current_request.httprequest, 'referrer', '')

                        # Buscar ID de la venta en la URL
                        import re
                        sale_id = None
                        for url_check in [url, referrer]:
                            if url_check:
                                match = re.search(r'id=(\d+).*model=sale\.order|model=sale\.order.*id=(\d+)', url_check)
                                if match:
                                    sale_id = int(match.group(1) or match.group(2))
                                    break

                        # Si encontramos el ID, crear un contexto fresco
                        if sale_id:
                            fresh_context = record.env.context.copy()
                            fresh_context.update({
                                'active_model': 'sale.order',
                                'active_id': sale_id,
                                'sale_order_id': sale_id,
                                'params': {'model': 'sale.order', 'id': sale_id}
                            })
                            # Crear un nuevo environment con el contexto fresco
                            record = record.with_context(fresh_context)

                    # Ejecutar automáticamente la subida a OneDrive con contexto fresco
                    result = record.action_upload_file()

                    # Si hay error en la subida, registrarlo pero no fallar la creación
                    if result and result.get('params', {}).get('type') in ['danger', 'warning']:
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.warning(
                            "Error automático subiendo archivo %s a OneDrive: %s",
                            record.upload_filename or record.name,
                            result.get('params', {}).get('message', 'Error desconocido')
                        )
                except Exception as e:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error(
                        "Excepción automática subiendo archivo %s a OneDrive: %s",
                        record.upload_filename or record.name,
                        str(e)
                    )

        return records
