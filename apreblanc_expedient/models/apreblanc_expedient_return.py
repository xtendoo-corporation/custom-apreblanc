from odoo import fields, models


class ApreblancExpedientReturn(models.Model):
    _name = 'apreblanc.expedient.return'
    _description = 'Expedient Return'
    _order = 'return_date desc'


    expedient_id = fields.Many2one(
        'apreblanc.expedient',
        string='Expedient',
        required=True,
        ondelete='cascade',
    )
    return_date = fields.Date(
        string='Return Date',
        required=True,
        default=fields.Date.today,
    )
    reason = fields.Text(
        string='Return Reason',
        required=True,
    )
