from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    probability = fields.Float(
        string='Probabilidad',
        default=0.0,
        help='Probabilidad de confirmación del pedido',
        tracking=True,
        copy=True,
        group_operator="avg"
    )
