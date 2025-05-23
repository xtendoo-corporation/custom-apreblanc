from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrderExpedientReturnHistory(models.Model):
    _name = 'sale.order.expedient.return.history'
    _description = 'Expedient Return History'
    _order = 'return_datetime desc'  # Ordenar por fecha y hora
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos básicos
    sale_order_id = fields.Many2one('sale.order', string='Expedient', required=True, ondelete='cascade')
    return_date = fields.Date(string='Return Date', required=True)
    return_datetime = fields.Datetime(string='Return Date & Time', required=True, tracking=True)
    return_time = fields.Float(string='Return Time', default=0.0)
    return_reason_id = fields.Many2one('expedient.return.reason', string='Return Reason', required=True)
    notes = fields.Text(string='Notes')
    user_id = fields.Many2one('res.users', string='User', tracking=True)

    # Método para proporcionar valores predeterminados de forma segura
    @api.model
    def default_get(self, fields_list):
        """Proporcionar valores predeterminados de manera segura"""
        defaults = super(SaleOrderExpedientReturnHistory, self).default_get(fields_list)

        # Añadir valores predeterminados de forma segura
        now = fields.Datetime.now()

        if 'return_date' in fields_list and 'return_date' not in defaults:
            defaults['return_date'] = now.date()

        if 'return_datetime' in fields_list and 'return_datetime' not in defaults:
            defaults['return_datetime'] = now

        if 'user_id' in fields_list and 'user_id' not in defaults:
            defaults['user_id'] = self.env.user.id

        return defaults

    # Sincronizar fecha cuando cambia datetime
    @api.onchange('return_datetime')
    def _onchange_return_datetime(self):
        """Sincronizar fecha cuando se cambia datetime"""
        if self.return_datetime:
            self.return_date = self.return_datetime.date()

    # Método create simple para registrar información
    @api.model
    def create(self, vals):
        # Sincronizar fecha con datetime si solo se proporciona uno
        if 'return_datetime' in vals and 'return_date' not in vals:
            datetime_val = fields.Datetime.to_datetime(vals['return_datetime'])
            vals['return_date'] = datetime_val.date()
        elif 'return_date' in vals and 'return_datetime' not in vals:
            # Si solo se proporciona fecha, crear datetime con hora actual
            date_val = fields.Date.to_date(vals['return_date'])
            current_time = fields.Datetime.now().time()
            vals['return_datetime'] = fields.Datetime.combine(date_val, current_time)

        _logger.info("Creando registro con valores: %s", vals)
        return super(SaleOrderExpedientReturnHistory, self).create(vals)
