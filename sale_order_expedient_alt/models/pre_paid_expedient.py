from odoo import api, fields, models, _, exceptions


class PrePaidExpedient(models.Model):
    _name = 'pre.paid.expedient'
    _description = 'Expediente Prepagado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name desc"
    _sql_constraints = [
        ('client_expedient_unique',
         'unique(client_id, expedient_number)',
         'La combinación de ID de Cliente y Número de Expediente debe ser única!')
    ]

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    expedient_number = fields.Char(
        string='Número de Expediente',
        copy=False,
        index=True,
        required=True,
        help="Identificador del expediente - debe ser único cuando se combina con ID de Cliente"
    )
    client_id = fields.Char(
        string='ID de Cliente',
        copy=False,
        index=True,
        required=True,
        help="Identificador del cliente - parte de la clave primaria junto con el Número de Expediente"
    )
    expedient_date = fields.Date(
        string='Fecha de Inicio',
        default=fields.Date.context_today,
        help='Fecha de inicio del expediente',
        tracking=True,
    )
    expedient_deadline = fields.Date(
        string='Fecha Límite',
        help='Fecha límite para completar el expediente',
        tracking=True,
    )
    expedient_manager_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
        help='Usuario responsable de gestionar este expediente',
    )
    expedient_state = fields.Selection([
        ('creada', 'Creado'),
        ('pendiente_documentacion', 'Pendiente de Documentación'),
        ('aprobada', 'Aprobado'),
        ('rechazada', 'Rechazado'),
        ('cancelada', 'Cancelado')
    ], string="Estado", default='creada', tracking=True,
        help="Estado actual del expediente prepagado")

    expedient_notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre este expediente',
        tracking=True,
    )

    # Campos específicos para expedientes prepagados
    initial_balance = fields.Float(
        string='Saldo Inicial',
        default=0.0,
        help='Saldo inicial del expediente prepagado',
        tracking=True,
    )
    current_balance = fields.Float(
        string='Saldo Actual',
        compute='_compute_current_balance',
        store=True,
        help='Saldo actual disponible',
    )

    # Relaciones con pedidos de venta
    sale_order_ids = fields.One2many(
        'sale.order',
        'pre_paid_expedient_id',
        string='Pedidos de Venta',
        help='Pedidos asociados a este expediente prepagado',
    )

    # Información del cliente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
    )
    partner_vat = fields.Char(related='partner_id.vat', string='NIF/CIF', readonly=True)
    partner_phone = fields.Char(related='partner_id.phone', string='Teléfono', readonly=True)
    partner_email = fields.Char(related='partner_id.email', string='Email', readonly=True)

    # Añadir el siguiente campo en el modelo pre.paid.expedient
    expedient_return_history_ids = fields.One2many(
        "pre.paid.expedient.return.history",
        "pre_paid_expedient_id",
        string="Historial de Devoluciones"
    )
    return_count = fields.Integer(
        string="Número de Devoluciones",
        compute="_compute_return_count",
        store=True
    )

    @api.depends('expedient_number', 'client_id')
    def _compute_name(self):
        for record in self:
            record.name = f"EP/{record.client_id}/{record.expedient_number}" if record.client_id and record.expedient_number else "Nuevo Expediente Prepagado"

    @api.depends('initial_balance', 'sale_order_ids.amount_total', 'sale_order_ids.state')
    def _compute_current_balance(self):
        for record in self:
            consumed = sum(order.amount_total for order in record.sale_order_ids if order.state in ('sale', 'done'))
            record.current_balance = record.initial_balance - consumed

    @api.depends("expedient_return_history_ids")
    def _compute_return_count(self):
        for record in self:
            record.return_count = len(record.expedient_return_history_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('pre.paid.expedient')

            # Verificar si la combinación ya existe
            if vals.get('client_id') and vals.get('expedient_number'):
                existing = self.env['pre.paid.expedient'].search([
                    ('client_id', '=', vals.get('client_id')),
                    ('expedient_number', '=', vals.get('expedient_number'))
                ], limit=1)

                if existing:
                    raise exceptions.ValidationError(_(
                        "Ya existe un expediente prepagado con ID de Cliente '%s' y Número de Expediente '%s'."
                    ) % (vals.get('client_id'), vals.get('expedient_number')))

        return super().create(vals_list)

    # Añadir métodos para cambiar estados
    def action_expedient_aprobada(self):
        self.ensure_one()
        self.write({'expedient_state': 'aprobada'})
        return True

    def action_expedient_rechazada(self):
        self.ensure_one()
        self.write({'expedient_state': 'rechazada'})
        return True

    def action_expedient_cancelada(self):
        self.ensure_one()
        self.write({'expedient_state': 'cancelada'})
        return True

    def action_expedient_pendiente_documentacion(self):
        self.ensure_one()
        self.write({'expedient_state': 'pendiente_documentacion'})
        return True
