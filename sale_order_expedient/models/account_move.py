from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    pre_paid_expedient_id = fields.Many2one(
        'pre.paid.expedient',
        string='Expediente Prepagado',
        help='Expediente prepagado relacionado con este documento contable',
        ondelete='restrict'
    )

    @api.model
    def _get_default_journal(self):
        """Extiende el método para usar diario de ventas para facturas de expedientes prepagados"""
        journal_type = self._context.get('journal_type', 'general')
        if self._context.get('default_pre_paid_expedient_id') and not self._context.get('default_journal_id'):
            if self._context.get('default_move_type') in ['out_invoice', 'out_refund']:
                journal_type = 'sale'
            elif self._context.get('default_move_type') in ['in_invoice', 'in_refund']:
                journal_type = 'purchase'

        return self.env['account.journal'].search([('type', '=', journal_type)], limit=1)
