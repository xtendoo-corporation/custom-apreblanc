from odoo import models, fields, api


class SaleOrderExpedientReturnHistory(models.Model):
    _name = 'sale.order.expedient.return.history'
    _description = 'Expedient Return History'
    _order = 'return_datetime desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Expedient',
        required=True,
        ondelete='cascade'
    )
    return_datetime = fields.Datetime(
        string='Date and Time',
        default=fields.Datetime.now,
        required=True
    )
    reason_id = fields.Many2one(
        'expedient.return.reason',
        string='Return Reason',
        required=True
    )
    notes = fields.Text(
        string='Additional Notes'
    )


