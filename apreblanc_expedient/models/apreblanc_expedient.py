from odoo import api, fields, models, _


class ApreblancExpedient(models.Model):
    _name = 'apreblanc.expedient'
    _description = 'Expedient'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reception_date desc'


    name = fields.Char(string='Reference', required=True, copy=False, default=lambda self: _('New'))
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        tracking=True,
    )
    is_expedient = fields.Boolean(
        string='Is Expedient',
        default=False,
        tracking=True,
        help='Check if this record is an expedient that can be returned',
    )
    reception_date = fields.Date(
        string='Reception Date',
        tracking=True,
    )
    start_date = fields.Date(
        string='Start Date',
        tracking=True,
    )
    closing_date = fields.Date(
        string='Closing Date',
        tracking=True,
    )
    expedient_return_ids = fields.One2many(
        'apreblanc.expedient.return',
        'expedient_id',
        string='Returns',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
        ('returned', 'Returned'),
    ], string='Status', default='draft', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'apreblanc_expedient_attachment_rel',
        'expedient_id',
        'attachment_id',
        string='Attachments',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('apreblanc.expedient') or _('New')
        return super().create(vals_list)

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_close(self):
        self.write({'state': 'closed', 'closing_date': fields.Date.today()})

    def action_return(self):
        self.write({'state': 'returned'})
