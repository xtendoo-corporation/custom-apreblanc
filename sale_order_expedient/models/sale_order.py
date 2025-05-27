from odoo import api, fields, models, _, exceptions


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _sql_constraints = [
        # Remove any constraints that enforce uniqueness on expedient_number alone
        # Keep only the composite constraint for both fields
        ('client_expedient_unique',
         'unique(client_id, expedient_number)',
         'The combination of Client ID and Expedient Number must be unique!')
    ]

    is_expedient = fields.Boolean(
        string='Is Expedient',
        help='Check if this sale order is an expedient',
        default=False,
    )
    # Expedient fields
    expedient_number = fields.Char(
        string='Expedient Number',
        copy=False,
        index=True,
        help="Identifier for the expedient - must be unique when combined with Client ID"
    )
    client_id = fields.Char(
        string='Client ID',
        copy=False,
        index=True,
        help="Client identifier - part of the primary key along with Expedient Number"
    )
    # El campo expedient_id se ha eliminado, expedient_number es ahora el identificador único
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
        ('creada', 'Creada'),
        ('pendiente_documentacion', 'Pending Documentation'),
        ('aprobada', 'Approved'),
        ('rechazada', 'Rejected'),
        ('cancelada', 'Canceled'),
    ], string='Expedient State', default='creada', tracking=True)

    expedient_notes = fields.Text(
        string='Notes',
        help='Additional notes about this expedient',
    )

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

    # Add a locked field to fix the view error
    locked = fields.Boolean(
        string='Locked',
        default=False,
        help='Technical field used in views',
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

            # Ensure client_id and expedient_number are set as primary key fields
            if vals.get('is_expedient') and not vals.get('client_id'):
                raise exceptions.ValidationError(_("Client ID is required for expedients."))
            if vals.get('is_expedient') and not vals.get('expedient_number'):
                raise exceptions.ValidationError(_("Expedient Number is required for expedients."))

            # Check if the combination already exists
            if vals.get('is_expedient') and vals.get('client_id') and vals.get('expedient_number'):
                existing = self.env['sale.order'].search([
                    ('client_id', '=', vals.get('client_id')),
                    ('expedient_number', '=', vals.get('expedient_number'))
                ], limit=1)

                if existing:
                    raise exceptions.ValidationError(_(
                        "An expedient with Client ID '%s' and Expedient Number '%s' already exists."
                    ) % (vals.get('client_id'), vals.get('expedient_number')))

        return super().create(vals_list)

    def write(self, vals):
        # Handle expedient state change to 'cancelada' from status bar
        if 'expedient_state' in vals and vals['expedient_state'] == 'cancelada':
            for record in self:
                # Only process if this is a state change to canceled
                if record.expedient_state != 'cancelada':
                    # Cancel the sale order if needed
                    if record.state != 'cancel':
                        record.action_cancel()

                    # Log both actions
                    record.message_post(
                        body=_("Expedient and sale order have been cancelled"),
                        message_type='notification'
                    )

        # If marking as expedient and has no expedient number
        if vals.get('is_expedient') and not self.expedient_number:
            vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        # Check if we're trying to modify a closed expedient
        for record in self:
            if record.is_expedient and record.expedient_state in ['aprobada', 'rechazada', 'cancelada']:
                # Always allow changes to these specific fields
                allowed_fields = {'message_ids', 'message_follower_ids', 'message_main_attachment_id',
                                  'activity_ids', 'activity_state', 'activity_user_id', 'activity_type_id',
                                  'activity_date_deadline', 'expedient_state'}

                # If trying to modify fields other than allowed ones
                if set(vals.keys()) - allowed_fields:
                    raise exceptions.UserError(_("This expedient is closed and cannot be modified."))

        return super().write(vals)

    # Methods for changing expedient state
    def action_expedient_aprobada(self):
        """Approve the expedient and track the change"""
        self.write({'expedient_state': 'aprobada'})
        for record in self:
            record.message_post(
                body=_("Expedient approved"),
                message_type='notification'
            )

    def action_expedient_rechazada(self):
        """Reject the expedient and track the change"""
        self.write({'expedient_state': 'rechazada'})
        for record in self:
            record.message_post(
                body=_("Expedient rejected"),
                message_type='notification'
            )

    def action_expedient_cancelada(self):
        """
        Cancel the expedient and the linked sale order.
        This method sets the expedient state to 'cancelada' and also
        cancels the underlying sale order.
        """
        for record in self:
            # First cancel the sale order itself using standard method
            if record.state != 'cancel':
                record.action_cancel()

            # Then update the expedient state
            record.expedient_state = 'cancelada'

            # Log both actions
            record.message_post(
                body=_("Expedient and sale order have been cancelled"),
                message_type='notification'
            )

    def action_expedient_pendiente_documentacion(self):
        """Set expedient as pending documentation and track the change"""
        self.write({'expedient_state': 'pendiente_documentacion'})
        for record in self:
            record.message_post(
                body=_("Expedient set to pending documentation"),
                message_type='notification'
            )

    def register_expedient_return(self):
        """Simplified method to register a return with full tracking"""
        self.ensure_one()
        if self.is_expedient and self.return_reason_id:
            # Create a history record when registering a return
            history_vals = {
                'sale_order_id': self.id,
                'return_datetime': fields.Datetime.now(),
                'return_reason_id': self.return_reason_id.id,
                'notes': self.return_notes,
                'user_id': self.env.user.id,
            }
            history_record = self.env['sale.order.expedient.return.history'].create(history_vals)

            # Post message in the sale order chatter
            self.message_post(
                body=_("Return registered: %s") % self.return_reason_id.name,
                message_type='notification'
            )

            # Clear the input fields after saving
            self.return_reason_id = False
            self.return_notes = False

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order.expedient.return.history',
                'res_id': history_record.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_sale_order_id': self.id}
            }
        return True
