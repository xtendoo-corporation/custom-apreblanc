from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_expedient = fields.Boolean(
        string='Es Expediente',
        help='Marcar si esta orden de venta es un expediente',
        default=False,
    )
