# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # Los adjuntos del chatter llegan de dos formas:
    #  - clip del chatter: create() directo con res_model/res_id del registro;
    #  - compositor: create() con res_model='mail.compose.message' y, al publicar el
    #    mensaje, write() para reasignarlo al registro.
    # Por eso se engancha create y write. Aqui solo se encola (sin red); la subida la
    # hace el cron de onedrive.attachment.sync.

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(v.get('res_model') and v.get('res_id') and not v.get('res_field') for v in vals_list):
            records._onedrive_enqueue()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'res_model' in vals or 'res_id' in vals:
            self._onedrive_enqueue()
        return res

    def _onedrive_enqueue(self):
        # Nunca debe romper la subida de un adjunto en Odoo.
        try:
            with self.env.cr.savepoint():
                self.env['onedrive.attachment.sync']._enqueue_attachments(self)
        except Exception:  # noqa: BLE001
            _logger.exception('[OneDrive adjuntos] no se pudo encolar el adjunto')
