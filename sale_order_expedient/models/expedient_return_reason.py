from odoo import fields, models


class ExpedientReturnReason(models.Model):
    _name = 'expedient.return.reason'
    _description = 'Return Reason'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        tracking=True,
        help="Used to order Return Reasons"
    )

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    description = fields.Text(
        string='Description',
        tracking=True
    )
