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

    expedient_type = fields.Selection([
        ('none', 'None'),
        ('pre_paid', 'Pre-pagado'),
        ('post_paid', 'Post-pagado'),
    ], string='Tipo de Expediente',
        default='none',
        help='Tipo de expediente de pre pago o post pago')

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

    # Related fields for customer information display
    partner_vat = fields.Char(related='partner_id.vat', string='VAT', readonly=True)
    partner_phone = fields.Char(related='partner_id.phone', string='Phone', readonly=True)
    partner_email = fields.Char(related='partner_id.email', string='Email', readonly=True)

    @api.depends('expedient_return_history_ids')
    def _compute_return_count(self):
        for order in self:
            order.return_count = len(order.expedient_return_history_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('expedient_type') and not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

            # Asegurar que client_id y expedient_number estén configurados como campos de clave primaria
            if vals.get('expedient_type') and not vals.get('client_id'):
                raise exceptions.ValidationError(_("Se requiere ID de cliente para expedientes."))
            if vals.get('expedient_type') and not vals.get('expedient_number'):
                raise exceptions.ValidationError(_("Se requiere Número de Expediente para expedientes."))

            # Verificar si la combinación ya existe
            if vals.get('expedient_type') and vals.get('client_id') and vals.get('expedient_number'):
                existing = self.env['sale.order'].search([
                    ('client_id', '=', vals.get('client_id')),
                    ('expedient_number', '=', vals.get('expedient_number'))
                ], limit=1)

                if existing:
                    raise exceptions.ValidationError(_(
                        "Ya existe un expediente con ID de Cliente '%s' y Número de Expediente '%s'."
                    ) % (vals.get('client_id'), vals.get('expedient_number')))
        return super().create(vals_list)

    def write(self, vals):
        # Track if expedient state is changing to a state that requires order confirmation
        confirm_states = ['aprobada', 'rechazada']
        needs_confirmation = (
            'expedient_state' in vals and
            vals['expedient_state'] in confirm_states and
            self.state == 'draft' and
            self.is_expedient
        )

        # Process the write operation normally
        result = super(SaleOrder, self).write(vals)

        # After write, confirm orders that need confirmation
        if needs_confirmation:
            # Set a context flag to prevent infinite loops if action_confirm also updates expedient_state
            if not self.env.context.get('expedient_confirmed'):
                self.with_context(expedient_confirmed=True).action_confirm()

        return result

    # Methods for changing expedient state
    def action_expedient_aprobada(self):
        """
        Approve the expedient and convert quotation to sale order.
        """
        for record in self:
            # First confirm the sale order if it's a quotation
            if record.state in ['draft', 'sent']:
                record.action_confirm()

            # Then update the expedient state
            record.expedient_state = 'aprobada'

            # Log the action
            record.message_post(
                body=_("Expedient approved and converted to sale order"),
                message_type='notification'
            )

    def action_expedient_rechazada(self):
        """
        Reject the expedient and convert quotation to sale order.
        """
        for record in self:
            # First confirm the sale order if it's a quotation
            if record.state in ['draft', 'sent']:
                record.action_confirm()

            # Then update the expedient state
            record.expedient_state = 'rechazada'

            # Log the action
            record.message_post(
                body=_("Expedient rejected and converted to sale order"),
                message_type='notification'
            )

    def action_expedient_cancelada(self):
        """
        Cancela el expediente y opcionalmente el pedido de venta vinculado.
        Para expedientes pre-pagados, no se cancela el pedido de venta.
        """
        for record in self:
            # Actualizar el estado del expediente primero
            record.expedient_state = 'cancelada'

            # Cancelar el pedido solo si NO es un expediente pre-pagado
            if record.expedient_type != 'pre_paid' and record.state != 'cancel':
                record.action_cancel()
                record.message_post(
                    body=_("Expediente y pedido de venta han sido cancelados"),
                    message_type='notification'
                )
            else:
                record.message_post(
                    body=_("Expediente cancelado (el pedido de venta permanece activo por ser de prepago)"),
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

    # Override action_confirm to handle expedient state change
    def action_confirm(self):
        # Check if we need to change expedient state
        expedient_state = self.env.context.get('set_expedient_state')
        result = super().action_confirm()

        # After confirmation, update the expedient state if needed
        if expedient_state and self.is_expedient:
            self.write({'expedient_state': expedient_state})
            # Post a message in the chatter
            state_name = dict(self._fields['expedient_state'].selection).get(expedient_state)
            self.message_post(
                body=_("Expedient marked as %s and converted to sale order") % state_name,
                message_type='notification'
            )

        return result
