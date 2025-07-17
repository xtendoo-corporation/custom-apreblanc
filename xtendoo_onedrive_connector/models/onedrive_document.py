from odoo import models, fields, api
from odoo.exceptions import UserError

class OnedriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'OneDrive Document'

    name = fields.Char(string='Name', required=True)
    is_folder = fields.Boolean(string='Is Folder', default=False)
    mime_type = fields.Char(string='MIME Type')
    size = fields.Float(string='Size')
    last_modified = fields.Datetime(string='Last Modified')
    onedrive_id = fields.Char(string='OneDrive ID', required=True)
    parent_id = fields.Many2one('onedrive.document', string='Parent Folder', ondelete='cascade')
    file_url = fields.Char(string='File URL')
    created_at = fields.Datetime(string='Created At')
    thumbnail = fields.Binary(string='Thumbnail')

    def navigate_to_folder(self):
        """ Navega a la carpeta seleccionada en OneDrive. """
        if not self.is_folder:
            raise UserError("Solo se puede navegar a carpetas.")

        # Retorna una acción para mostrar los documentos dentro de la carpeta seleccionada
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documentos en ' + self.name,
            'res_model': 'onedrive.document',
            'view_mode': 'tree,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }

    def download_file(self):
        """Descarga el archivo desde OneDrive usando la URL almacenada."""
        if self.is_folder:
            raise UserError("Solo se pueden descargar archivos, no carpetas.")
        if not self.file_url:
            raise UserError("No hay URL de archivo disponible para descargar.")
        return {
            'type': 'ir.actions.act_url',
            'url': self.file_url,
            'target': 'new',
        }
