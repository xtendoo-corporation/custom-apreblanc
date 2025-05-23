from odoo import api, fields, models, _, exceptions


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_expedient = fields.Boolean(
        string='Is Expedient',
        help='Check if this sale order is an expedient',
        default=False,
    )
    # Expedient fields
    expedient_number = fields.Char(
        string='Expedient Number',
        copy=False,
        help="Unique number assigned to the expedient"
    )
    expedient_date = fields.Date(
        string='Start Date',
        help='Start date of the expedient',
    )
    expedient_deadline = fields.Date(
        string='Deadline',
        help='Deadline to complete the expedient',
    )
    expedient_manager_id = fields.Many2one(
        'res.users',
        string='Manager',
        help='User responsible for managing this expedient',
    )
    expedient_state = fields.Selection([
        ('nueva', 'Nueva'),
        ('pendiente_documentacion', 'Pending Documentation'),
        ('aprobada', 'Approved'),
        ('rechazada', 'Rejected'),
        ('cancelada', 'Canceled'),
    ], string='Expedient State', default='nueva', tracking=True)

    is_expedient_closed = fields.Boolean(
        string='Expedient Closed',
        compute='_compute_is_expedient_closed',
        store=True
    )

    expedient_notes = fields.Text(
        string='Notes',
        help='Additional notes about this expedient',
    )

    @api.depends('expedient_state')
    def _compute_is_expedient_closed(self):
        for order in self:
            order.is_expedient_closed = order.expedient_state in ['rechazada', 'cancelada', 'aprobada']

    # Current return fields
    return_reason_id = fields.Many2one(
        'expedient.return.reason',
        string='Return Reason',
    )
    return_notes = fields.Text(
        string='Additional Notes',
        help='Additional notes for the return',
    )
    # Return history
    expedient_return_history_ids = fields.One2many(
        'sale.order.expedient.return.history',
        'sale_order_id',
        string='Return History',
    )
    # Add computed field to count returns
    return_count = fields.Integer(
        string='Return Count',
        compute='_compute_return_count',
        store=False
    )

    @api.depends('expedient_return_history_ids')
    def _compute_return_count(self):
        for order in self:
            order.return_count = len(order.expedient_return_history_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_expedient') and not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')
        return super().create(vals_list)

    def write(self, vals):
        # If marking as expedient and has no expedient number
        if vals.get('is_expedient') and not self.expedient_number:
            vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')
        # Check if we're trying to modify a closed expedient
        for record in self:
            if record.is_expedient and record.is_expedient_closed:
                # Always allow changes to these specific fields
                allowed_fields = {'message_ids', 'message_follower_ids', 'message_main_attachment_id',
                                  'activity_ids', 'activity_state', 'activity_user_id', 'activity_type_id',
                                  'activity_date_deadline', 'expedient_state'}

                # If trying to modify fields other than allowed ones
                if set(vals.keys()) - allowed_fields:
                    # Check if we're just changing the state to a closed state
                    if set(vals.keys()) - allowed_fields != {'is_expedient_closed'} or not vals.get('is_expedient_closed', False):
                        raise exceptions.UserError(_("This expedient is closed and cannot be modified."))

        return super().write(vals)

    # # Methods for changing expedient state (maintain for compatibility)
    # def action_expedient_aprobada(self):
    #     self.write({'expedient_state': 'aprobada'})
    #
    # def action_expedient_rechazada(self):
    #     self.write({'expedient_state': 'rechazada'})
    #
    # def action_expedient_cancelada(self):
    #     self.write({'expedient_state': 'cancelada'})
    #
    # def action_expedient_pendiente_documentacion(self):
    #     self.write({'expedient_state': 'pendiente_documentacion'})
    #
    # # Simplified method to register a return
    # def register_expedient_return(self):
    #     self.ensure_one()
    #     if self.is_expedient and self.return_reason_id:
    #         # Create a history record when registering a return
    #         history_vals = {
    #             'sale_order_id': self.id,
    #             'return_datetime': fields.Datetime.now(),
    #             'reason_id': self.return_reason_id.id,
    #             'notes': self.return_notes,
    #         }
    #         self.env['sale.order.expedient.return.history'].create(history_vals)
    #         # Clear the input fields after saving
    #         self.return_reason_id = False
    #         self.return_notes = False
    #     return True
