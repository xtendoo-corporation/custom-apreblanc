from odoo import models, fields

class ExpedientReturnReason(models.Model):
    _name = 'expedient.return.reason'
    _description = 'Expedient Return Reason'
    _order = 'sequence, id'

    name = fields.Char(
        string='Reason',
        required=True,
    )
    description = fields.Text(
        string='Description',
        help='Detailed description of this return reason'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order reasons'
    )
