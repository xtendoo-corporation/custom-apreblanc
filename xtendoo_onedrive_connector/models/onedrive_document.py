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
        # Lógica para subir un archivo a OneDrive
        return True

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
