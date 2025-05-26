from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrderExpedientReturnHistory(models.Model):
    _name = 'sale.order.expedient.return.history'
    _description = 'Expedient Return History'
    _order = 'return_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos básicos
    sale_order_id = fields.Many2one('sale.order', string='Expedient', required=True, ondelete='cascade', tracking=True)
    return_date = fields.Datetime(string='Return Date & Time', required=True, tracking=True)
    return_reason_id = fields.Many2one('expedient.return.reason', string='Return Reason', required=True, tracking=True)
    notes = fields.Text(string='Notes', tracking=True)
    user_id = fields.Many2one('res.users', string='User', tracking=True)

    # Método para proporcionar valores predeterminados de forma segura
    @api.model
    def default_get(self, fields_list):
        """Proporcionar valores predeterminados de manera segura"""
        defaults = super(SaleOrderExpedientReturnHistory, self).default_get(fields_list)

        # Añadir valores predeterminados de forma segura
        now = fields.Datetime.now()

        if 'return_date' in fields_list and 'return_date' not in defaults:
            defaults['return_date'] = now

        if 'user_id' in fields_list and 'user_id' not in defaults:
            defaults['user_id'] = self.env.user.id

        return defaults

    # Método create mejorado para tracking completo
    @api.model
    def create(self, vals):
        _logger.info("Creando registro con valores: %s", vals)
        record = super(SaleOrderExpedientReturnHistory, self).create(vals)

        # Post a message in the return history chatter
        if record.return_reason_id and record.sale_order_id:
            message = _("Return history entry created: %s") % record.return_reason_id.name
            if record.notes:
                message += _("\nNotes: %s") % record.notes
            record.message_post(body=message, message_type='notification')

            # Also post a message in the sale order chatter
            record.sale_order_id.message_post(
                body=_("New return entry added to expedient: %s") % record.return_reason_id.name,
                message_type='notification'
            )

        return record

    def write(self, vals):
        """Override write to add tracking message when return history is updated."""
        result = super(SaleOrderExpedientReturnHistory, self).write(vals)

        # Track significant changes
        if any(field in vals for field in ['return_reason_id', 'return_date', 'notes']):
            for record in self:
                message = _("Return history entry updated")
                record.message_post(body=message, message_type='notification')

        return result

    def unlink(self):
        """Override unlink to add tracking message when return history is deleted."""
        for record in self:
            if record.sale_order_id:
                record.sale_order_id.message_post(
                    body=_("Return history entry deleted: %s") % (record.return_reason_id.name or _("Unknown reason")),
                    message_type='notification'
                )
        return super(SaleOrderExpedientReturnHistory, self).unlink()
