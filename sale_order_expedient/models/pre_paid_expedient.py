from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PrePaidExpedient(models.Model):
    _name = 'pre.paid.expedient'
    _description = 'Expediente Prepagado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expedient_date desc, id desc'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
    )
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla de Presupuesto',
        domain="[('partner_id', '=', partner_id)]",
    )
    client_id = fields.Char(
        string='ID Cliente',
        required=True,
        tracking=True,
    )
    expedient_number = fields.Char(
        string='Número de Expediente',
        required=True,
        tracking=True,
    )
    expedient_date = fields.Date(
        string='Fecha de Inicio',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    expedient_deadline = fields.Date(
        string='Fecha Límite',
        tracking=True,
    )
    expedient_manager_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )
    expedient_state = fields.Selection([
        ('creada', 'Creada'),
        ('pendiente_documentacion', 'Pendiente Documentación'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
    ], string='Estado', default='creada', tracking=True)
    expedient_notes = fields.Text(
        string='Notas',
        tracking=True,
    )
    # Historial de devoluciones
    expedient_return_history_ids = fields.One2many(
        'pre.paid.expedient.return.history',
        'pre_paid_expedient_id',
        string='Historial de Devoluciones',
    )
    # Campos financieros
    initial_balance = fields.Monetary(
        string='Saldo Inicial',
        currency_field='currency_id',
        required=True,
        default=0.0,
        tracking=True,
    )
    current_balance = fields.Monetary(
        string='Saldo Actual',
        currency_field='currency_id',
        compute='_compute_current_balance',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
    )

    # Relacionado con pedidos de venta en lugar de facturas
    sale_order_ids = fields.One2many(
        'sale.order',
        'pre_paid_expedient_id',
        string='Pedidos de Venta',
    )
    sale_order_count = fields.Integer(
        string='Número de Pedidos',
        compute='_compute_sale_order_count',
    )
    # Mantenemos account_move para compatibilidad con el modelo original
    account_move_ids = fields.Many2many(
        'account.move',
        string='Asientos Contables',
        compute='_compute_account_moves',
    )
    account_move_count = fields.Integer(
        string='Número de Asientos',
        compute='_compute_account_move_count',
    )

    _sql_constraints = [
        ('client_expedient_unique',
         'unique(client_id, expedient_number)',
         'La combinación de ID Cliente y Número de Expediente debe ser única!')
    ]

    @api.depends('partner_id', 'expedient_number', 'client_id')
    def _compute_name(self):
        for expedient in self:
            if expedient.partner_id and expedient.expedient_number and expedient.client_id:
                expedient.name = f"{expedient.partner_id.name} - {expedient.client_id}/{expedient.expedient_number}"
            else:
                expedient.name = "Nuevo Expediente"

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        for expedient in self:
            expedient.sale_order_count = len(expedient.sale_order_ids)

    @api.depends('sale_order_ids')
    def _compute_account_moves(self):
        for expedient in self:
            # Obtener todos los asientos contables relacionados con los pedidos de venta
            moves = self.env['account.move']
            for order in expedient.sale_order_ids:
                if order.invoice_ids:
                    moves |= order.invoice_ids
            expedient.account_move_ids = moves

    @api.depends('account_move_ids')
    def _compute_account_move_count(self):
        for expedient in self:
            expedient.account_move_count = len(expedient.account_move_ids)

    @api.depends('initial_balance', 'sale_order_ids.amount_total', 'sale_order_ids.state')
    def _compute_current_balance(self):
        for expedient in self:
            # El saldo actual es el saldo inicial menos la suma de los pedidos confirmados
            confirmed_orders = expedient.sale_order_ids.filtered(
                lambda o: o.state in ['sale', 'done']
            )
            used_amount = sum(order.amount_total for order in confirmed_orders)
            expedient.current_balance = expedient.initial_balance - used_amount

    def action_view_sale_orders(self):
        """Ver los pedidos de venta asociados a este expediente."""
        self.ensure_one()
        action = {
            'name': _('Pedidos de Venta'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('pre_paid_expedient_id', '=', self.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_expedient_type': 'pre_paid',
                'default_pre_paid_expedient_id': self.id,
                'default_client_id': self.client_id,
                'default_expedient_number': self.expedient_number,
            }
        }
        return action

    def action_view_account_moves(self):
        """Ver los asientos contables asociados a este expediente."""
        self.ensure_one()
        action = {
            'name': _('Asientos Contables'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.account_move_ids.ids)],
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Verificar que la combinación client_id y expedient_number sea única
            if vals.get('client_id') and vals.get('expedient_number'):
                existing = self.env['pre.paid.expedient'].search([
                    ('client_id', '=', vals.get('client_id')),
                    ('expedient_number', '=', vals.get('expedient_number'))
                ], limit=1)

                if existing:
                    raise ValidationError(_(
                        "Ya existe un expediente con ID de Cliente '%s' y Número de Expediente '%s'."
                    ) % (vals.get('client_id'), vals.get('expedient_number')))

        return super().create(vals_list)

    def action_expedient_aprobada(self):
        """Aprobar el expediente."""
        for record in self:
            record.expedient_state = 'aprobada'
            record.message_post(
                body=_("Expediente aprobado"),
                message_type='notification'
            )

    def action_expedient_rechazada(self):
        """Rechazar el expediente."""
        for record in self:
            record.expedient_state = 'rechazada'
            record.message_post(
                body=_("Expediente rechazado"),
                message_type='notification'
            )

    def action_expedient_pendiente_documentacion(self):
        """Marcar expediente como pendiente de documentación."""
        for record in self:
            record.expedient_state = 'pendiente_documentacion'
            record.message_post(
                body=_("Expediente marcado como pendiente de documentación"),
                message_type='notification'
            )

    def action_expedient_cancelada(self):
        """Cancelar el expediente."""
        for record in self:
            record.expedient_state = 'cancelada'
            record.message_post(
                body=_("Expediente cancelado"),
                message_type='notification'
            )
