from odoo import models, fields, api
import requests

class OneDriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'OneDrive Document'

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

    @api.model
    def action_sync_onedrive(self):
        """
        Método llamado desde la interfaz para sincronizar con OneDrive
        """
        try:
            # Usar el servicio mejorado de OneDrivee
            service = self.env['onedrive.service']
            result = service.sync_onedrive_files()

            # Mostrar notificación y recargar la vista
            if result['success']:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    'params': {
                        'title': 'Sincronización Exitosa',
                        'type': 'success',
                        'message': result['message'],
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    'params': {
                        'title': 'Error en la Sincronización',
                        'type': 'danger',
                        'message': result['error'],
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                'params': {
                    'title': 'Error en la Sincronización',
                    'type': 'danger',
                    'message': str(e),
                    'sticky': False,
                }
            }

    def action_download_file(self):
        """Descargar archivo directamente desde OneDrive usando la URL almacenada"""
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

        # Usar directamente la URL de OneDrive que ya funciona en el navegador
        return {
            'type': 'ir.actions.act_url',
            'url': self.file_url,
            'target': 'self',
        }

    def action_upload_file(self):
        """Subir archivo a OneDrive con estructura de carpetas específica"""
        # Variable configurable para el nombre de la carpeta raíz
        ROOT_FOLDER_NAME = "odoo"

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

            # Obtener el nombre de la venta (asumiendo que viene del contexto o está relacionado)
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

            # Paso 2: Verificar/crear carpeta de la venta dentro de "odoo"
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

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '¡Éxito!',
                    'message': f'Archivo "{self.upload_filename}" subido correctamente a OneDrive en {ROOT_FOLDER_NAME}/{sale_name}/',
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

    def _get_sale_name(self):
        """Obtener el nombre de la venta desde el contexto o relación"""
        # Intentar obtener desde el contexto
        if self.env.context.get('sale_name'):
            return self.env.context.get('sale_name')

        # Intentar obtener desde el active_id si viene de una venta
        if self.env.context.get('active_model') == 'sale.order' and self.env.context.get('active_id'):
            sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
            return sale_order.name if sale_order.exists() else None

        # Si no se encuentra, usar un nombre genérico con timestamp
        from datetime import datetime
        return f"documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _ensure_folder_exists(self, folder_name, parent_folder_id, headers):
        """Verificar si existe una carpeta, si no existe la crea"""
        try:
            # Construir URL para buscar carpetas
            if parent_folder_id:
                search_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{parent_folder_id}/children'
            else:
                search_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'

            # Buscar la carpeta existente - corregir el filtro
            filter_url = f"{search_url}?$filter=name eq '{folder_name}'"
            response = requests.get(filter_url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                folders = [item for item in data.get('value', []) if item.get('folder') is not None]
                if folders:
                    # La carpeta existe, devolver su ID
                    return folders[0]['id']

            # La carpeta no existe, crearla SIN rename para evitar duplicados
            create_data = {
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail"  # Cambiar a "fail" para no crear duplicados
            }

            create_response = requests.post(search_url, headers=headers, json=create_data, timeout=30)

            if create_response.status_code == 201:
                return create_response.json()['id']
            elif create_response.status_code == 409:
                # Si falla porque ya existe (conflicto), buscar nuevamente
                response = requests.get(filter_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    folders = [item for item in data.get('value', []) if item.get('folder') is not None]
                    if folders:
                        return folders[0]['id']
                raise Exception(f"Carpeta {folder_name} existe pero no se puede encontrar")
            else:
                raise Exception(f"Error creando carpeta {folder_name}: {create_response.status_code} - {create_response.text}")

        except Exception as e:
            raise Exception(f"Error en _ensure_folder_exists para {folder_name}: {str(e)}")

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
                    # Ejecutar automáticamente la subida a OneDrive
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
