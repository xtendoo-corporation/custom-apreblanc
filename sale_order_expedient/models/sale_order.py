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
        help='Fecha y hora en que se inició el proceso del expediente (distinta a la fecha de creación)',
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
    # Reemplazar el campo computado por un campo normal
    return_count = fields.Integer(
        string='Return Count',
        default=0,
        help='Número de devoluciones asociadas al expediente'
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

    # Nuevos campos para expedientes
    complejidad_proyecto = fields.Selection([
        ('simple', 'Simple'),
        ('complejo', 'Complejo')
    ], string='Complejidad del Proyecto', default='simple',
       help='Indica la complejidad del proyecto del expediente')

    numero_personas = fields.Integer(
        string='Número de Personas',
        help='Número de personas involucradas en el expediente',
        default=1
    )

    # Campo para fecha de inicio del expediente (completamente separado de date_order)
    expedient_start_date = fields.Datetime(
        string='Fecha de Inicio del Expediente',
        help='Fecha y hora en que se inició el proceso del expediente (diferente a la fecha de creación)',
        copy=False,  # No copiar al duplicar el registro
    )

    # Campo para el conteo de devoluciones - ahora usando un campo computado no almacenado
    return_count = fields.Integer(
        string='Devoluciones',
        compute='_compute_return_count',
        store=False  # No almacenar para evitar problemas con la base de datos
    )

    @api.depends('expedient_return_history_ids')
    def _compute_return_count(self):
        """Computa el número de devoluciones asociadas al expediente"""
        for record in self:
            record.return_count = len(record.expedient_return_history_ids)

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
    # Reemplazar el campo computado por un campo normal
    return_count = fields.Integer(
        string='Return Count',
        default=0,
        help='Número de devoluciones asociadas al expediente'
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

    # Nuevos campos para expedientes
    complejidad_proyecto = fields.Selection([
        ('simple', 'Simple'),
        ('complejo', 'Complejo')
    ], string='Complejidad del Proyecto', default='simple',
       help='Indica la complejidad del proyecto del expediente')

    numero_personas = fields.Integer(
        string='Número de Personas',
        help='Número de personas involucradas en el expediente',
        default=1
    )

    # Campo para fecha de inicio del expediente (completamente separado de date_order)
    expedient_start_date = fields.Datetime(
        string='Fecha de Inicio del Expediente',
        help='Fecha y hora en que se inició el proceso del expediente (diferente a la fecha de creación)',
        copy=False,  # No copiar al duplicar
    )

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    @api.model
    def create(self, vals):
        """Sobrescribir método create para manejar expedientes"""
        # Validar valores para expedientes
        if vals.get('expedient_type') and vals['expedient_type'] != 'none':
            # Verificar si client_id es un campo Many2one o un campo Char
            client_id_field = self._fields.get('client_id')
            if client_id_field and client_id_field.type == 'many2one' and 'client_id' in vals:
                if isinstance(vals['client_id'], str) and vals['client_id']:
                    # Buscar el partner por nombre
                    partner = self.env['res.partner'].search([('name', '=', vals['client_id'])], limit=1)
                    if partner:
                        vals['client_id'] = partner.id
                    else:
                        # Si no se encuentra, podríamos crear uno nuevo o dejar vacío
                        vals['client_id'] = False

            # Asegurarse de que expedient_start_date está establecido
            if not vals.get('expedient_start_date'):
                vals['expedient_start_date'] = fields.Datetime.now()

        # Llamar al método original
        return super().create(vals)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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
        """Al cambiar el tipo de expediente, actualizar campos relevantes"""
        # Si cambia a un tipo de expediente válido, establecer la fecha de inicio
        # if self.expedient_type in ['post_paid', 'pre_paid'] and not self.expedient_start_date:
        #     self.expedient_start_date = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        """No establecer fecha de inicio automáticamente para que el usuario la pueda ingresar"""
        # for vals in vals_list:
        #     # Si es un expediente prepagado, FORZAR estado 'sale' desde el inicio
        #     if vals.get('expedient_type') == 'pre_paid':
        #         # Establecer estado sale pero expedient_state en creada
        #         vals['state'] = 'sale'
        #         vals['expedient_state'] = 'creada'
        #         vals['expedient_date_end'] = False
        #         _logger.info("Creando expediente prepagado directamente en estado 'sale' con expedient_state 'creada'")

        #     # Gestión del número de expediente según su tipo
        #     if vals.get('expedient_type') == 'post_paid' and not vals.get('expedient_number'):
        #         vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')

        #     # Establecer fecha de inicio automáticamente para expedientes
        #     if vals.get('expedient_type') in ['post_paid', 'pre_paid'] and not vals.get('expedient_start_date'):
        #         vals['expedient_start_date'] = fields.Datetime.now()

        return super().create(vals_list)

    @api.model
    def _validate_expedient_creation(self, vals):
        """Valida los datos antes de crear un expediente"""
        # Verificar campos obligatorios para expedientes
        required_fields = ['partner_id', 'client_id', 'expedient_type']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            raise ValidationError(_("Los siguientes campos son obligatorios: %s") % ", ".join(missing_fields))

        # Validar que el client_id sea un campo de texto válido
        if vals.get('client_id') and not isinstance(vals['client_id'], str):
            raise ValidationError(_("El campo Client ID debe ser un texto válido"))

        # Verificar si ya existe un expediente con el mismo número
        if vals.get('expedient_number'):
            existing = self.search([
                ('expedient_number', '=', vals['expedient_number']),
                ('expedient_type', '!=', 'none')
            ], limit=1)
            if existing:
                raise ValidationError(_("Ya existe un expediente con el número %s") % vals['expedient_number'])

        return True

    # ...existing code...

    @api.depends('expedient_start_date', 'expedient_date_end', 'expedient_state')
    def _compute_expedient_resolution_time(self):
        """Calcula el tiempo transcurrido entre la fecha de inicio y fin del expediente"""
        for order in self:
            if order.expedient_type == 'none':
                order.expedient_resolution_time = False
                continue

            # Solo calcular si tenemos ambas fechas y el estado es apropiado
            if (order.expedient_start_date and order.expedient_date_end and
                order.expedient_state in ['aprobada', 'rechazada']):

                start_date = fields.Datetime.from_string(order.expedient_start_date)
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

    # Si
