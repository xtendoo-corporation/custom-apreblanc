from odoo import api, fields, models, _, exceptions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


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

    # Relación con expedientes prepagados
    pre_paid_expedient_id = fields.Many2one(
        'pre.paid.expedient',
        string='Expediente Prepagado',
        domain="[('partner_id', '=', partner_id)]",
        help='Relación con expediente prepagado',
    )

    # El campo expedient_id se ha eliminado, expedient_number es ahora el identificador único
    expedient_date_start = fields.Datetime(
        string='Fecha de Inicio del Expediente',
        default=lambda self: fields.Datetime.now(),  # Esto establecerá automáticamente la fecha y hora actual
        help='Fecha y hora en que se inició el expediente',
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

    # Campos de fecha y hora para control de tiempo
    expedient_date_end = fields.Datetime(
        string='Fin de Expediente',
        help='Fecha y hora en que se finalizó el expediente (aprobación o rechazo)',
    )
    # Modificar el campo para que sea calculado
    expedient_resolution_time = fields.Char(
        string='Tiempo de Resolución',
        compute='_compute_expedient_resolution_time',
        store=True,
        help="Tiempo transcurrido entre la creación y la resolución del expediente"
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

    @api.depends('date_order', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.date_order and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.date_order)
                end_date = fields.Datetime.from_string(order.expedient_date_end)

                # Asegurarse de que la fecha de fin es posterior a la de inicio
                if end_date and start_date and end_date >= start_date:
                    # Calcular la diferencia
                    delta = relativedelta(end_date, start_date)

                    # Formatear el resultado en un formato legible
                    parts = []
                    if delta.years > 0:
                        parts.append(f"{delta.years} {'año' if delta.years == 1 else 'años'}")
                    if delta.months > 0:
                        parts.append(f"{delta.months} {'mes' if delta.months == 1 else 'meses'}")
                    if delta.days > 0:
                        parts.append(f"{delta.days} {'día' if delta.days == 1 else 'días'}")
                    if delta.hours > 0:
                        parts.append(f"{delta.hours} {'hora' if delta.hours == 1 else 'horas'}")

                    order.expedient_resolution_time = ", ".join(parts) if parts else "Menos de una hora"
                else:
                    order.expedient_resolution_time = "Fecha de fin inválida"
            else:
                if order.expedient_state in ['creada', 'pendiente_documentacion']:
                    order.expedient_resolution_time = "En proceso"
                else:
                    order.expedient_resolution_time = False

    # Si es necesario, también podemos actualizar la fecha de fin automáticamente
    # cuando cambia el estado del expediente
    @api.onchange('expedient_state')
    def _onchange_expedient_state(self):
        """Actualiza la fecha de fin cuando el expediente pasa a estado aprobado o rechazado"""
        for order in self:
            if order.expedient_type != 'none' and order.expedient_state in ['aprobada', 'rechazada']:
                if not order.expedient_date_end:
                    order.expedient_date_end = fields.Datetime.now()

    @api.onchange('expedient_type')
    def _onchange_expedient_type(self):
        """Al cambiar el tipo de expediente, reiniciar los campos correspondientes"""
        if self.expedient_type == 'pre_paid':
            # Para prepagados, usamos la relación con el modelo de expedientes prepagados
            self.client_id = False
            self.expedient_number = False
            self.expedient_date_start = False
            self.expedient_manager_id = False
            self.expedient_state = 'creada'
            self.expedient_notes = False
        elif self.expedient_type == 'none':
            # Si no es expediente, limpiar todos los campos
            self.client_id = False
            self.expedient_number = False
            self.expedient_date_start = False
            self.expedient_manager_id = False
            self.expedient_state = 'creada'
            self.expedient_notes = False
            self.pre_paid_expedient_id = False

    @api.onchange('pre_paid_expedient_id')
    def _onchange_pre_paid_expedient(self):
        """Al seleccionar un expediente prepagado, actualizar el tipo de expediente"""
        if self.pre_paid_expedient_id:
            self.expedient_type = 'pre_paid'
            # Autocompletar los campos desde el expediente prepagado
            self.client_id = self.pre_paid_expedient_id.client_id
            self.expedient_number = self.pre_paid_expedient_id.expedient_number

    @api.model_create_multi
    def create(self, vals_list):
        """Establece fecha de inicio al crear expedientes"""
        for vals in vals_list:
            # Si es un expediente prepagado, verificar que tenga relación con el expediente
            if vals.get('expedient_type') == 'pre_paid' and not vals.get('pre_paid_expedient_id'):
                raise exceptions.ValidationError(_("Para expedientes prepagados, debe seleccionar un expediente prepagado existente."))

            # Gestión del número de expediente según su tipo
            if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

            # Resto de validaciones para expedientes
            if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('client_id'):
                raise exceptions.ValidationError(_("Se requiere ID de cliente para expedientes."))
            if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
                raise exceptions.ValidationError(_("Se requiere Número de Expediente para expedientes."))

            # Verificar combinación única solo para expedientes post-pagados
            if vals.get('expedient_type') == 'post_paid' and vals.get('client_id') and vals.get('expedient_number'):
                existing = self.env['sale.order'].search([
                    ('client_id', '=', vals.get('client_id')),
                    ('expedient_number', '=', vals.get('expedient_number')),
                    ('expedient_type', '=', 'post_paid')
                ], limit=1)

                if existing:
                    raise exceptions.ValidationError(_(
                        "Ya existe un expediente con ID de Cliente '%s' y Número de Expediente '%s'."
                    ) % (vals.get('client_id'), vals.get('expedient_number')))

            # Establecer fecha de inicio automáticamente para expedientes
            if vals.get('expedient_type') in ['post_paid', 'pre_paid']:
                # Siempre registrar la fecha y hora exacta de apertura del expediente
                vals['expedient_date_start'] = fields.Datetime.now()
                # Registrar en el log que se ha creado un expediente con su fecha de apertura
                _logger.info(
                    "Creando expediente tipo %s con fecha de apertura: %s",
                    vals.get('expedient_type'),
                    vals['expedient_date_start']
                )

        # Crear las órdenes de venta
        orders = super().create(vals_list)

        # Para cada expediente creado, registrar un mensaje en el chatter
        for order in orders:
            if order.expedient_type in ['post_paid', 'pre_paid']:
                order.message_post(
                    body=_("Expediente abierto el %s") %
                    fields.Datetime.to_string(order.expedient_date_start),
                    message_type='notification'
                )

        # Confirmar automáticamente los expedientes pre-pagados
        pre_paid_orders = orders.filtered(lambda o: o.expedient_type == 'pre_paid')
        if pre_paid_orders:
            pre_paid_orders.with_context(auto_confirm_prepaid=True).action_confirm()

        return orders

    def write(self, vals):
        """
        Override write to handle expedient state changes and set the end date automatically
        when the state changes to 'aprobada' or 'rechazada'.
        """
        # Para depuración
        _logger.info("Método write llamado con valores: %s", vals)

        # Si se está cambiando el estado a aprobada, rechazada o cancelada,
        # registrar automáticamente la fecha y hora de finalización
        if 'expedient_state' in vals and vals['expedient_state'] in ['aprobada', 'rechazada', 'cancelada']:
            _logger.info("Detectado cambio a estado final: %s", vals['expedient_state'])

            # Forzar la actualización de fecha_fin independientemente de si ya está en vals
            now = fields.Datetime.now()
            vals['expedient_date_end'] = now
            _logger.info("Estableciendo fecha de fin: %s", now)

        # Ejecutar el write original
        result = super().write(vals)

        # Verificar cambios de estado después del write para logging y mensajes
        if 'expedient_state' in vals and vals['expedient_state'] in ['aprobada', 'rechazada', 'cancelada']:
            for record in self:
                # Verificar si la fecha de fin está establecida
                if not record.expedient_date_end:
                    _logger.warning("Fecha de fin no establecida después del cambio de estado para expediente %s", record.name)
                    # Forzar actualización directa
                    record._cr.execute(
                        "UPDATE sale_order SET expedient_date_end = %s WHERE id = %s",
                        (fields.Datetime.now(), record.id)
                    )
                    # Invalidar caché para que vea el cambio
                    record.invalidate_cache(['expedient_date_end'])
                    _logger.info("Fecha de fin forzada para expediente %s", record.name)

                # Registrar mensaje en el chatter con la fecha de fin
                if record.expedient_date_end and not self.env.context.get('skip_expedient_end_date_message'):
                    estado = dict(self._fields['expedient_state'].selection).get(vals['expedient_state'])
                    record.with_context(skip_expedient_end_date_message=True).message_post(
                        body=_("Expediente marcado como %s el %s. Tiempo de resolución: %s") %
                        (estado, fields.Datetime.to_string(record.expedient_date_end), record.expedient_resolution_time or ''),
                        message_type='notification'
                    )

        return result

    # Añadir un constraint para forzar la fecha de fin cuando el estado es final
    @api.constrains('expedient_state')
    def _check_expedient_date_end(self):
        """Asegurar que expedient_date_end esté establecido cuando el estado es final"""
        for record in self:
            if record.expedient_state in ['aprobada', 'rechazada', 'cancelada'] and not record.expedient_date_end:
                # Si el estado es final pero no hay fecha de fin, establecerla
                _logger.info("Estableciendo fecha de fin faltante para expediente %s en estado %s",
                             record.name, record.expedient_state)
                record.write({'expedient_date_end': fields.Datetime.now()})

    # Añadir un método para forzar la actualización de expedient_date_end
    @api.model
    def _cron_update_missing_expedient_end_dates(self):
        """Cron job para actualizar fechas de fin faltantes en expedientes con estado final"""
        expedients = self.search([
            ('expedient_type', '!=', 'none'),
            ('expedient_state', 'in', ['aprobada', 'rechazada', 'cancelada']),
            '|', ('expedient_date_end', '=', False), ('expedient_date_end', '=', None)
        ])

        if expedients:
            _logger.info("Encontrados %s expedientes con estado final y sin fecha de fin", len(expedients))
            for expedient in expedients:
                expedient.write({'expedient_date_end': fields.Datetime.now()})
                expedient.message_post(
                    body=_("Fecha de fin establecida automáticamente por el sistema para estado %s") %
                    dict(expedient._fields['expedient_state'].selection).get(expedient.expedient_state),
                    message_type='notification'
                )

            return len(expedients)
        return 0

    # Override del método action_expedient_pendiente_documentacion
    def action_expedient_pendiente_documentacion(self):
        """Set expedient as pending documentation and track the change"""
        # Si hay una fecha de fin, la eliminamos ya que es un estado intermedio
        vals = {'expedient_state': 'pendiente_documentacion'}
        if any(record.expedient_date_end for record in self):
            vals['expedient_date_end'] = False
            _logger.info("Eliminando fecha de fin al cambiar a estado pendiente")

        self.write(vals)

        for record in self:
            record.message_post(
                body=_("Expedient set to pending documentation"),
                message_type='notification'
            )

    # Methods for changing expedient state
    def action_expedient_aprobada(self):
        """
        Approve the expedient and convert quotation to sale order.
        """
        for record in self:
            # Registrar fecha y hora de aprobación
            now = fields.Datetime.now()
            record.write({'expedient_date_end': now})

            # First confirm the sale order if it's a quotation
            if record.state in ['draft', 'sent']:
                record.action_confirm()

            # Then update the expedient state
            record.expedient_state = 'aprobada'

            # Forzar recálculo del tiempo de resolución
            record.invalidate_cache(['expedient_resolution_time'])
            record._compute_expedient_resolution_time()

            # Log the action con la fecha de fin
            resolution_time = record.expedient_resolution_time or 'No disponible'
            record.message_post(
                body=_("Expediente marcado como %s el %s. Tiempo de resolución: %s") %
                ('Approved', fields.Datetime.to_string(now), resolution_time),
                message_type='notification'
            )

    def action_expedient_rechazada(self):
        """
        Reject the expedient and convert quotation to sale order.
        """
        for record in self:
            # Registrar fecha y hora de rechazo
            now = fields.Datetime.now()
            record.write({'expedient_date_end': now})

            # First confirm the sale order if it's a quotation
            if record.state in ['draft', 'sent']:
                record.action_confirm()

            # Then update the expedient state
            record.expedient_state = 'rechazada'

            # Log the action con la fecha de fin
            record.message_post(
                body=_("Expediente rechazado el %s. Tiempo de resolución: %s") %
                (fields.Datetime.to_string(now), record.expedient_resolution_time or ''),
                message_type='notification'
            )

    def action_expedient_cancelada(self):
        """
        Cancela el expediente y opcionalmente el pedido de venta vinculado.
        Para expedientes pre-pagados, no se cancela el pedido de venta.
        """
        for record in self:
            # Registrar fecha y hora de cancelación
            now = fields.Datetime.now()
            record.write({'expedient_date_end': now})

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
                # Añadir información sobre la fecha de cancelación en el mensaje
                message = _("Expediente cancelado el %s") % fields.Datetime.to_string(now)
                if record.expedient_type != 'pre_paid' and record.state != 'cancel':
                    message += _(". El pedido de venta también ha sido cancelado")
                else:
                    message += _(" (el pedido de venta permanece activo por ser de prepago)")

                record.message_post(body=message, message_type='notification')

    def action_expedient_pendiente_documentacion(self):
        """Set expedient as pending documentation and track the change"""
        # No establecemos fecha de fin ya que es un estado intermedio
        self.write({'expedient_state': 'pendiente_documentacion'})
        for record in self:
            record.message_post(
                body=_("Expedient set to pending documentation"),
                message_type='notification'
            )

    def register_expedient_return(self):
        """Simplified method to register a return with full tracking"""
        self.ensure_one()
        if self.expedient_type != 'none' and self.return_reason_id:  # Reemplazamos is_expedient
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
        # Verificar saldo suficiente para expedientes prepagados
        for order in self:
            if order.expedient_type == 'pre_paid' and order.pre_paid_expedient_id:
                if order.amount_total > order.pre_paid_expedient_id.current_balance:
                    raise exceptions.ValidationError(_(
                        "No hay saldo suficiente en el expediente prepagado. "
                        "Saldo actual: %.2f, Importe del pedido: %.2f"
                    ) % (order.pre_paid_expedient_id.current_balance, order.amount_total))

        # Continuar con la confirmación normal
        result = super().action_confirm()

        # Check if we need to change expedient state
        expedient_state = self.env.context.get('set_expedient_state')

        # After confirmation, update the expedient state if needed
        if expedient_state and self.expedient_type != 'none':  # Reemplazamos is_expedient
            self.write({'expedient_state': expedient_state})
            # Post a message in the chatter
            state_name = dict(self._fields['expedient_state'].selection).get(expedient_state)
            self.message_post(
                body=_("Expedient marked as %s and converted to sale order") % state_name,
                message_type='notification'
            )

        return result

    def action_register_return(self):
        """Register a return for this expedient"""
        self.ensure_one()

        # Create return history entry
        return_entry = self.env['sale.order.expedient.return.history'].create({
            'sale_order_id': self.id,
            'return_reason_id': self.return_reason_id.id if self.return_reason_id else False,
            'return_date': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'notes': self.return_notes or '',
        })

        # Update return count
        self.return_count = len(self.expedient_return_history_ids)

        # Para expedientes pre-pagados, cambiar automáticamente a pendiente de documentación
        if self.expedient_type == 'pre_paid' and self.expedient_state not in ['aprobada', 'rechazada']:
            self.expedient_state = 'pendiente_documentacion'
            self.message_post(
                body=_("Expediente marcado como pendiente de documentación debido a devolución registrada"),
                message_type='notification'
            )

        # Log the return
        reason_name = return_entry.return_reason_id.name if return_entry.return_reason_id else _('Unknown reason')
        self.message_post(body=_('Return registered: %s') % reason_name)

        # Clear the return fields after registration
        self.write({
            'return_reason_id': False,
            'return_notes': False,
        })

        return True

    @api.model
    def create(self, vals):
        """Override create to handle expedient creation logic"""
        # Set expedient manager if not provided
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            if not vals.get('expedient_manager_id'):
                vals['expedient_manager_id'] = self.env.user.id

            # Set expedient date if not provided
            if not vals.get('expedient_date_start'):
                vals['expedient_date_start'] = fields.Date.today()

            # Set initial expedient state
            if not vals.get('expedient_state'):
                vals['expedient_state'] = 'creada'

        result = super().create(vals)

        # Para expedientes pre-pagados, verificar si hay devoluciones previas
        if result.expedient_type == 'pre_paid' and result.return_count > 0:
            if result.expedient_state in ['creada']:
                result.expedient_state = 'pendiente_documentacion'
                result.message_post(
                    body=_("Estado automáticamente cambiado a pendiente de documentación debido a devoluciones existentes"),
                    message_type='notification'
                )

        return result

    def _auto_confirm_prepaid_expedient(self, record):
        """Helper method to auto confirm pre-paid expedients"""
        if record.expedient_type == 'pre_paid' and record.state == 'draft':
            try:
                record.action_confirm()
                record.message_post(body=_('Expediente pre-pagado confirmado automáticamente como pedido de venta'))
            except Exception as e:
                record.message_post(body=_('Error al confirmar automáticamente el expediente pre_pagado: %s') % str(e))
                _logger.error("Error confirming pre-paid expedient: %s", str(e))
        return record
