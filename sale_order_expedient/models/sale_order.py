from odoo import api, fields, models, _, exceptions
from odoo.exceptions import ValidationError
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

    # Nuevos campos para expedientes
    parts_involved = fields.Integer(
        string='Partes Implicadas',
        default=1,
        help='Número de partes implicadas en el expediente'
    )

    expedient_difficulty = fields.Selection([
        ('simple', 'Simple'),
        ('complex', 'Complejo')
    ], string='Dificultad del Expediente', 
       default='simple',
       help='Nivel de dificultad del expediente'
    )

    account_numbers = fields.Integer(
        string='Números de Cuentas',
        default=1,
        help='Número de cuentas relacionadas con el expediente'
    )

    # Campos existentes
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

    # Añadir campo para verificar si usuario es administrador
    is_expedient_admin = fields.Boolean(
        string='Es Administrador de Expedientes',
        compute='_compute_is_expedient_admin',
        store=False,
    )

    @api.depends()
    def _compute_is_expedient_admin(self):
        """Determina si el usuario actual es administrador y puede modificar expedientes finalizados"""
        # Usar el nuevo grupo definido en security.xml
        is_admin = self.env.user.has_group('sale_order_expedient.group_expedient_admin') or self.env.user.has_group('base.group_system')
        for record in self:
            record.is_expedient_admin = is_admin

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
        store=True  # Cambiar a True para permitir su uso en vistas pivot
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
        """Al cambiar el tipo de expediente, reiniciar los campos correspondientes y forzar estado si es prepagado"""
        if self.expedient_type == 'pre_paid':
            # Para prepagados, usamos la relación con el modelo de expedientes prepagados
            self.client_id = False
            self.expedient_number = False
            self.expedient_date_start = False
            self.expedient_manager_id = False
            self.expedient_state = 'creada'  # Cambiado de 'aprobada' a 'creada'
            self.expedient_notes = False
            # Forzar estado sale y fecha fin
            self.state = 'sale'
            # No establecer fecha de fin ya que el expediente está en estado 'creada'
            self.expedient_date_end = False
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
        """Establece fecha de inicio al crear expedientes y confirma los pre-pagados"""
        # Mantener un registro de expedientes prepagados para procesar después
        prepaid_ids = []

        for vals in vals_list:
            # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
            if vals.get('expedient_type') == 'pre_paid':
                # Establecer estado sale pero expedient_state en creada
                vals['state'] = 'sale'
                vals['expedient_state'] = 'creada'
                vals['expedient_date_end'] = False
                _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

            # Gestión del número de expediente según su tipo
            if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

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

        # FORZAR CONFIRMACIÓN INMEDIATA para expedientes prepagados
        for order in orders:
            if order.expedient_type == 'pre_paid':
                prepaid_ids.append(order.id)
                # Verificar inmediatamente el estado
                if order.state != 'sale':
                    _logger.warning("Expediente prepagado %s creado sin estado 'sale'. Corrigiendo...", order.name)
                    # Usar write con contexto especial en lugar de SQL directo
                    order.with_context(force_prepaid_state=True).write({
                        'state': 'sale',
                        'expedient_state': 'creada',
                        'expedient_date_end': False
                    })
                    order.message_post(
                        body=_("Estado 'sale' forzado inmediatamente después de la creación"),
                        message_type='notification'
                    )

        # Si hay expedientes prepagados, hacer una verificación adicional
        if prepaid_ids:
            # Verificar nuevamente después de los cambios
            double_check_orders = self.browse(prepaid_ids)
            for order in double_check_orders:
                if order.state != 'sale':
                    _logger.error("¡URGENTE! Expediente prepagado %s sigue sin estado 'sale'. Último intento...", order.name)
                    # Usar super con un contexto especial para evitar validaciones
                    order.with_context(bypass_prepaid_checks=True).write({'state': 'sale'})

        # Para cada expediente creado, registrar un mensaje en el chatter
        for order in orders:
            if order.expedient_type in ['post_paid', 'pre_paid']:
                order.message_post(
                    body=_("Expediente abierto el %s") %
                    fields.Datetime.to_string(order.expedient_date_start),
                    message_type='notification'
                )

        # Confirmar automáticamente TODOS los expedientes pre-pagados SIN EXCEPCIÓN
        pre_paid_orders = orders.filtered(lambda o: o.expedient_type == 'pre_paid')
        if pre_paid_orders:
            _logger.info("Confirmando automáticamente %s expedientes pre-pagados", len(pre_paid_orders))
            for order in pre_paid_orders:
                # Verificar saldo solo para advertir, no para bloquear
                if order.pre_paid_expedient_id and order.amount_total > order.pre_paid_expedient_id.current_balance:
                    order.message_post(
                        body=_("ADVERTENCIA: No hay saldo suficiente en el expediente pre-pagado. "
                              "Saldo actual: %.2f, Importe del pedido: %.2f. "
                              "El pedido se ha confirmado pero debe revisarse.") %
                              (order.pre_paid_expedient_id.current_balance, order.amount_total),
                        message_type='notification'
                    )

                # SIEMPRE confirmar, usando múltiples métodos si es necesario
                try:
                    # Preservar el estado del expediente como 'creada' mientras se confirma como pedido de venta
                    orig_expedient_state = order.expedient_state
                    super(SaleOrder, order).action_confirm()
                    order.write({
                        'expedient_state': 'creada',
                        'expedient_date_end': False
                    })
                except Exception as e:
                    _logger.error("Error en confirmación estándar: %s", str(e))
                    try:
                        # 2. Método alternativo - SQL directo
                        self.env.cr.execute(
                            """UPDATE sale_order
                               SET state = 'sale', expedient_state = 'aprobada'
                               WHERE id = %s""", (order.id,))
                        order.write({'expedient_date_end': fields.Datetime.now()})
                        order.message_post(body=_('Confirmado mediante SQL tras error en método estándar'))
                    except Exception as e2:
                        _logger.error("Error en método alternativo: %s", str(e2))
                        # 3. Último recurso - forzar atributos
                        order.state = 'sale'
                        order.expedient_state = 'aprobada'
                        order.expedient_date_end = fields.Datetime.now()
                        order.message_post(body=_('Estado confirmado forzado tras múltiples errores'))

        return orders

    def write(self, vals):
        """
        Override write to prevent modifications on approved/rejected expedients
        unless the user is an administrator.
        """
        # Si se está forzando un estado de expediente prepagado, permitirlo
        if self.env.context.get('force_prepaid_state') or self.env.context.get('bypass_prepaid_checks') or self.env.context.get('bypass_all_constraints'):
            return super().write(vals)

        # Verificar si hay expedientes en estado final que se están intentando modificar
        locked_expedients = self.filtered(lambda r: r.expedient_type in ['post_paid', 'pre_paid'] and
                                         r.expedient_state in ['aprobada', 'rechazada'] and
                                         not self.env.user.has_group('sale_order_expedient.group_expedient_admin') and
                                         not self.env.user.has_group('base.group_system'))

        # Si hay expedientes bloqueados y se intenta cambiar campos sensibles
        if locked_expedients and any(field for field in vals.keys() if field not in ['message_follower_ids', 'activity_ids', 'message_ids']):
            # Lista de campos que siempre se pueden cambiar (relacionados con mensajería, actividades, etc.)
            always_writable = ['message_follower_ids', 'activity_ids', 'message_ids',
                             'message_main_attachment_id', 'website_message_ids']

            # Filtrar solo los campos que realmente están intentando modificar (no los de mensajería)
            restricted_fields = [field for field in vals.keys() if field not in always_writable]

            if restricted_fields:
                # Verificar si se está intentando cambiar el estado del expediente
                if 'expedient_state' in vals:
                    raise exceptions.AccessError(_(
                        "No tiene permisos para cambiar el estado de expedientes que están aprobados o rechazados. "
                        "Solo un administrador puede realizar esta acción."
                    ))
                else:
                    raise exceptions.AccessError(_(
                        "No tiene permisos para modificar expedientes que están aprobados o rechazados. "
                        "Solo un administrador puede realizar esta acción. "
                        "Campos que intentó modificar: %s"
                    ) % ", ".join(restricted_fields))

        # Si está intentando cambiar el estado del expediente a un estado anterior
        if 'expedient_state' in vals and any(record.expedient_state in ['aprobada', 'rechazada'] for record in self):
            # Verificar si el usuario no es administrador
            if not self.env.user.has_group('base.group_system') and not self.env.user.has_group('sales_team.group_sale_manager'):
                raise exceptions.AccessError(_(
                    "No tiene permisos para cambiar el estado de expedientes aprobados o rechazados. "
                    "Solo un administrador puede realizar esta acción."
                ))

        # Prevenir cambio de estado en expedientes prepagados
        pre_paid_orders = self.filtered(lambda r: r.expedient_type == 'pre_paid')

        # Si intentan cambiar el estado de un expediente prepagado a algo que no sea 'sale'
        if pre_paid_orders and 'state' in vals and vals['state'] != 'sale':
            # Dividir el proceso para expedientes prepagados y otros
            other_orders = self - pre_paid_orders

            # Procesar órdenes regulares normalmente
            result = True
            if other_orders:
                result = super(SaleOrder, other_orders).write(vals)

            # Para expedientes prepagados, mantener 'sale' y solo actualizar otros campos
            prepaid_vals = {k: v for k, v in vals.items() if k != 'state'}
            if prepaid_vals:
                super(SaleOrder, pre_paid_orders).write(prepaid_vals)

            # Registrar en el log el intento de cambio de estado
            for order in pre_paid_orders:
                _logger.warning(
                    "Intento de cambiar estado de expediente prepagado %s de 'sale' a '%s'. Cambio ignorado.",
                    order.name, vals['state']
                )
                order.message_post(
                    body=_("AVISO: Se intentó cambiar el estado del expediente prepagado a '%s', pero los expedientes prepagados deben permanecer siempre en estado 'sale'.") % vals['state'],
                    message_type='notification'
                )

            return result

        # Si no se intenta cambiar el estado o no hay expedientes prepagados, proceso normal
        return super().write(vals)

    # Override de los métodos de cambio de estado para verificar permisos
    def action_expedient_pendiente_documentacion(self):
        """Set expedient as pending documentation and track the change"""
        # Verificar si algún expediente está en estado final y el usuario no es administrador
        locked_expedients = self.filtered(lambda r: r.expedient_state in ['aprobada', 'rechazada'] and
                                         not r.is_expedient_admin)
        if locked_expedients:
            raise exceptions.AccessError(_(
                "No tiene permisos para cambiar el estado de expedientes aprobados o rechazados. "
                "Solo un administrador puede realizar esta acción."
            ))

        # Continuar con la acción original
        return super().action_expedient_pendiente_documentacion()

    def action_expedient_aprobada(self):
        """Approve the expedient and convert quotation to sale order."""
        # Los expedientes rechazados no pueden cambiar a aprobados a menos que sea administrador
        locked_expedients = self.filtered(lambda r: r.expedient_state == 'rechazada' and
                                         not r.is_expedient_admin)
        if locked_expedients:
            raise exceptions.AccessError(_(
                "No tiene permisos para aprobar expedientes que ya fueron rechazados. "
                "Solo un administrador puede realizar esta acción."
            ))

        return super().action_expedient_aprobada()

    def action_expedient_rechazada(self):
        """Reject the expedient and convert quotation to sale order."""
        # Los expedientes aprobados no pueden cambiar a rechazados a menos que sea administrador
        locked_expedients = self.filtered(lambda r: r.expedient_state == 'aprobada' and
                                         not r.is_expedient_admin)
        if locked_expedients:
            raise exceptions.AccessError(_(
                "No tiene permisos para rechazar expedientes que ya fueron aprobados. "
                "Solo un administrador puede realizar esta acción."
            ))

        return super().action_expedient_rechazada()

    def action_expedient_cancelada(self):
        """Cancel the expedient and optionally the linked sale order."""
        # Los expedientes aprobados/rechazados no pueden cancelarse a menos que sea administrador
        locked_expedients = self.filtered(lambda r: r.expedient_state in ['aprobada', 'rechazada'] and
                                         not r.is_expedient_admin)
        if locked_expedients:
            raise exceptions.AccessError(_(
                "No tiene permisos para cancelar expedientes que ya fueron aprobados o rechazados. "
                "Solo un administrador puede realizar esta acción."
            ))

        return super().action_expedient_cancelada()

    # Añadir un constraint para forzar la fecha de fin cuando el estado es final
    @api.constrains('expedient_state')
    def _check_expedient_date_end(self):
        """Asegurar que expedient_date_end esté establecido cuando el estado es final"""
        for record in self:
            # Solo para estados finales que no sean expedientes prepagados
            if record.expedient_type != 'pre_paid' and \
               record.expedient_state in ['aprobada', 'rechazada', 'cancelada'] and \
               not record.expedient_date_end:
                # Si el estado es final pero no hay fecha de fin, establecerla
                _logger.info("Estableciendo fecha de fin faltante para expediente %s en estado %s",
                             record.name, record.expedient_state)
                record.write({'expedient_date_end': fields.Datetime.now()})

    @api.constrains('expedient_state')
    def _check_expedient_confirmed(self):
        """Asegurar que expedientes en estado final estén confirmados como pedido"""
        for record in self:
            if record.expedient_type in ['post_paid', 'pre_paid'] and \
               record.expedient_state in ['aprobada', 'rechazada'] and \
               record.state != 'sale':
                _logger.warning(
                    "Expediente %s en estado %s pero no confirmado como pedido. Forzando confirmación.",
                    record.name, record.expedient_state
                )
                # Forzar estado 'sale'
                record.write({'state': 'sale'})
                record.message_post(
                    body=_("Estado 'sale' forzado automáticamente al detectar expediente en estado final no confirmado"),
                    message_type='notification'
                )

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
                # Intentar confirmar de manera normal
                try:
                    record.action_confirm()
                except Exception as e:
                    _logger.error("Error al confirmar expediente %s: %s", record.name, str(e))
                    # Forzar estado 'sale' directamente si falla la confirmación normal
                    record.write({'state': 'sale'})
                    record.message_post(
                        body=_("Error en confirmación estándar, estado 'sale' forzado manualmente: %s") % str(e),
                        message_type='notification'
                    )

            # Asegurar que cualquier expediente (postpagado o prepagado) esté en estado 'sale'
            if record.expedient_type in ['post_paid', 'pre_paid'] and record.state != 'sale':
                _logger.info("Forzando estado 'sale' para expediente %s al ser aprobado", record.name)
                record.write({'state': 'sale'})
                record.message_post(
                    body=_("Expediente convertido automáticamente a pedido de venta al ser aprobado"),
                    message_type='notification'
                )

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
                # Intentar confirmar de manera normal
                try:
                    record.action_confirm()
                except Exception as e:
                    _logger.error("Error al confirmar expediente rechazado %s: %s", record.name, str(e))
                    # Forzar estado 'sale' directamente si falla la confirmación normal
                    record.write({'state': 'sale'})
                    record.message_post(
                        body=_("Error en confirmación estándar al rechazar, estado 'sale' forzado: %s") % str(e),
                        message_type='notification'
                    )

            # Asegurar que cualquier expediente (postpagado o prepagado) esté en estado 'sale'
            if record.expedient_type in ['post_paid', 'pre_paid'] and record.state != 'sale':
                _logger.info("Forzando estado 'sale' para expediente %s al ser rechazado", record.name)
                record.write({'state': 'sale'})
                record.message_post(
                    body=_("Expediente convertido automáticamente a pedido de venta al ser rechazado"),
                    message_type='notification'
                )

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
        """Override para garantizar que los expedientes prepago siempre se confirmen"""
        # Para expedientes prepagados, SIEMPRE confirmar sin validaciones
        pre_paid_orders = self.filtered(lambda o: o.expedient_type == 'pre_paid')
        regular_orders = self - pre_paid_orders

        result = True

        # Procesar órdenes regulares con validaciones normales
        if regular_orders:
            result = super(SaleOrder, regular_orders).action_confirm()

        # Para expedientes prepagados, FORZAR estado 'sale' sin importar nada más
        for order in pre_paid_orders:
            _logger.info("Confirmando expediente prepagado %s", order.name)

            # PRIMERA OPCIÓN: Método estándar con try/except
            try:
                # Intentar confirmación estándar (solo para state, no cambiar expedient_state)
                orig_expedient_state = order.expedient_state
                super(SaleOrder, order).action_confirm()
                # Restaurar el estado del expediente a 'creada'
                if order.expedient_state != orig_expedient_state:
                    order.write({'expedient_state': 'creada', 'expedient_date_end': False})
            except Exception as e:
                _logger.error("Error en confirmación estándar: %s. Aplicando método de respaldo.", str(e))

                # SEGUNDA OPCIÓN: Método de respaldo con escritura directa
                try:
                    # Forzar todos los valores críticos
                    order.write({
                        'state': 'sale',  # Esto es lo más importante - el estado 'sale'
                        'expedient_state': 'creada',  # Siempre creada para prepagados
                        'expedient_date_end': False,  # Sin fecha fin
                    })
                    order.message_post(
                        body=_("Expediente prepagado forzado a estado 'sale'"),
                        message_type='notification'
                    )
                except Exception as e2:
                    _logger.error("Error en método de respaldo: %s. Aplicando método de emergencia.", str(e2))

                    # TERCERA OPCIÓN: Método de emergencia con SQL directo (siempre funcionará)
                    try:
                        self.env.cr.execute(
                            """UPDATE sale_order
                               SET state = 'sale',
                                   expedient_state = 'creada',
                                   expedient_date_end = NULL,
                                   write_date = NOW() AT TIME ZONE 'UTC'
                               WHERE id = %s""", (order.id,))
                        order.message_post(
                            body=_("Expediente prepagado forzado a estado 'sale' mediante SQL directo"),
                            message_type='notification'
                        )
                    except Exception as e3:
                        _logger.critical("¡Error crítico al confirmar expediente prepagado! %s", str(e3))

        # Los expedientes pre-pagados siempre deben estar en estado 'creada'
        for order in pre_paid_orders:
            if order.expedient_state != 'creada':
                order.write({
                    'expedient_state': 'creada',
                    'expedient_date_end': False
                })
                order.message_post(
                    body=_("Expediente pre-pagado restaurado a estado 'creada' automáticamente"),
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

            # Si es expediente prepagado, forzar estado 'sale' y 'creada'
            if vals.get('expedient_type') == 'pre_paid':
                vals['state'] = 'sale'
                vals['expedient_state'] = 'creada'
                vals['expedient_date_end'] = False
                _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

            # Set expedient date if not provided
            if not vals.get('expedient_date_start'):
                vals['expedient_date_start'] = fields.Datetime.now()

            # Set initial expedient state if not already set
            if not vals.get('expedient_state'):
                vals['expedient_state'] = 'creada'

        # Call super to create the sale order
        order = super(SaleOrder, self).create(vals)

        # For pre-paid expedients, force the state to 'sale' immediately
        if order.expedient_type == 'pre_paid':
            _logger.info("Forzando estado 'sale' para expediente prepagado %s al ser creado", order.name)

            # Usar write con contexto especial en lugar de SQL directo
            order.with_context(force_prepaid_state=True).write({
                'state': 'sale',
                'expedient_state': 'creada',
                'expedient_date_end': False
            })

            # Verificar si el cambio se aplicó correctamente
            # Usar self.env.cache.invalidate() en lugar de order.invalidate_cache()
            self.env.cache.invalidate()
            order = self.browse(order.id)  # Obtener registro fresco

            if order.state != 'sale' or order.expedient_state != 'creada':
                _logger.warning(
                    "El expediente prepagado %s no está en estado correcto después de creación. "
                    "Estado actual: %s, Expedient state: %s. Intentando forzar de nuevo.",
                    order.name, order.state, order.expedient_state
                )
                # Último intento con contexto aún más permisivo
                order.with_context(bypass_all_constraints=True).write({
                    'state': 'sale',
                    'expedient_state': 'creada',
                    'expedient_date_end': False
                })

            order.message_post(
                body=_("Expediente pre-pagado creado como pedido de venta confirmado con estado de expediente 'creada'"),
                message_type='notification'
            )

            # Procesamiento post-creación específico para expedientes pre-pagados
            if order.pre_paid_expedient_id:
                # Verificar saldo solo para advertir, no para bloquear
                if order.amount_total > order.pre_paid_expedient_id.current_balance:
                    order.message_post(
                        body=_("ADVERTENCIA: El saldo disponible (%.2f) es menor que el importe del pedido (%.2f)") %
                             (order.pre_paid_expedient_id.current_balance, order.amount_total),
                        message_type='notification'
                    )

            return order

        # Para cada expediente creado, registrar un mensaje en el chatter
        if order.expedient_type in ['post_paid', 'pre_paid']:
            order.message_post(
                body=_("Expediente abierto el %s") %
                fields.Datetime.to_string(order.expedient_date_start),
                message_type='notification'
            )

        return order

    @api.model
    def force_prepaid_expedients_sale_state(self):
        """Forzar estado 'sale' para todos los expedientes prepagados con expedient_state 'creada'"""
        # Buscar todos los expedientes prepagados que no estén en estado 'sale' o expedient_state 'creada'
        broken_expedients = self.search([
            ('expedient_type', '=', 'pre_paid'),
            '|',
            ('state', '!=', 'sale'),
            ('expedient_state', '!=', 'creada')
        ])

        if broken_expedients:
            _logger.warning("Encontrados %s expedientes prepagados en estado incorrecto. Corrigiendo...", len(broken_expedients))
            for expedient in broken_expedients:
                # Usar write con contexto especial en lugar de SQL directo
                expedient.with_context(force_prepaid_state=True).write({
                    'state': 'sale',
                    'expedient_state': 'creada',
                    'expedient_date_end': False
                })
                expedient.message_post(
                    body=_("Estado 'sale' y expedient_state 'creada' forzados por verificación automática"),
                    message_type='notification'
                )
            return len(broken_expedients)
        return 0

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

    @api.model
    def _cron_check_expedient_state_consistency(self):
        """Verificar y corregir expedientes que deberían estar en estado 'sale'"""
        expedients = self.search([
            ('expedient_type', 'in', ['post_paid', 'pre_paid']),
            ('expedient_state', 'in', ['aprobada', 'rechazada']),
            ('state', '!=', 'sale')
        ])

        if expedients:
            _logger.info("Encontrados %s expedientes en estado final que no están en 'sale'", len(expedients))
            for expedient in expedients:
                expedient.write({'state': 'sale'})
                expedient.message_post(
                    body=_("Estado 'sale' forzado por tarea programada de consistencia para expediente en estado %s") %
                    dict(expedient._fields['expedient_state'].selection).get(expedient.expedient_state),
                    message_type='notification'
                )
            return len(expedients)
        return 0

    @api.model
    def _cron_force_prepaid_sale_state(self):
        """Cron job para forzar estado 'sale' en expedientes prepagados"""
        return self.force_prepaid_expedients_sale_state()

    @api.constrains('parts_involved', 'account_numbers')
    def _check_positive_values(self):
        """Asegurar que los valores numéricos sean siempre mayores que 0"""
        for record in self:
            if record.expedient_type != 'none':  # Solo verificar para expedientes
                if record.parts_involved <= 0:
                    raise ValidationError(_('El número de partes implicadas debe ser mayor que 0.'))
                if record.account_numbers <= 0:
                    raise ValidationError(_('El número de cuentas debe ser mayor que 0.'))
                    raise ValidationError(_('El número de partes implicadas debe ser mayor que 0.'))
                if record.account_numbers <= 0:
                    raise ValidationError(_('El número de cuentas debe ser mayor que 0.'))
