from odoo import models, fields, api


class SaleOrderExpedientReturnHistory(models.Model):
    _name = 'sale.order.expedient.return.history'
    _description = 'Historial de Devoluciones de Expedientes'
    _order = 'return_date desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Expediente',
        required=True,
        ondelete='cascade'
    )
    return_date = fields.Date(
        string='Fecha de Devolución',
        default=fields.Date.today,
        required=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Registrado por',
        default=lambda self: self.env.user,
        required=True
    )
    reason = fields.Selection([
        ('completed', 'Completado'),
        ('rejected', 'Rechazado'),
        ('canceled', 'Cancelado'),
        ('error', 'Error en documentación'),
        ('other', 'Otro motivo')
    ], string='Motivo de Devolución',
       required=True)
    notes = fields.Text(
        string='Notas',
        help='Observaciones sobre esta devolución'
    )
    return_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada')
    ], string='Estado', default='pending', required=True)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_expedient = fields.Boolean(
        string='Es Expediente',
        help='Marcar si esta orden de venta es un expediente',
        default=False,
    )

    # Nuevos campos para expedientes
    expedient_number = fields.Char(
        string='Número de Expediente',
        copy=False,
        help="Número único asignado al expediente"
    )

    expedient_date = fields.Date(
        string='Fecha de Inicio',
        help='Fecha de inicio del expediente',
    )

    expedient_deadline = fields.Date(
        string='Fecha Límite',
        help='Fecha límite para completar el expediente',
    )

    expedient_manager_id = fields.Many2one(
        'res.users',
        string='Responsable',
        help='Usuario responsable de gestionar este expediente',
    )

    expedient_state = fields.Selection([
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
        ('pendiente_documentacion', 'Pendiente documentación adicional')
    ], string='Estado del Expediente', default='pendiente_documentacion',
       help="Estado actual del expediente")

    expedient_notes = fields.Text(
        string='Notas del Expediente',
        help='Notas adicionales sobre el expediente'
    )

    # Nuevos campos para devolución de expedientes
    expedient_return_date = fields.Date(
        string='Fecha de Devolución',
        help='Fecha en la que se devuelve el expediente',
    )

    expedient_return_user_id = fields.Many2one(
        'res.users',
        string='Devuelto por',
        help='Usuario que registra la devolución del expediente',
    )

    expedient_return_reason = fields.Selection([
        ('completed', 'Completado'),
        ('rejected', 'Rechazado'),
        ('canceled', 'Cancelado'),
        ('error', 'Error en documentación'),
        ('other', 'Otro motivo')
    ], string='Motivo de Devolución',
       help="Motivo por el cual se devuelve el expediente")

    expedient_return_notes = fields.Text(
        string='Notas de Devolución',
        help='Notas adicionales sobre la devolución del expediente'
    )

    expedient_return_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada')
    ], string='Estado de Devolución', default='pending',
       help="Estado actual de la devolución del expediente")

    # Add the one2many relationship to the history
    expedient_return_history_ids = fields.One2many(
        'sale.order.expedient.return.history',
        'sale_order_id',
        string='Historial de Devoluciones'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_expedient') and not vals.get('expedient_number'):
                vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')
        return super().create(vals_list)

    def write(self, vals):
        # Si se está marcando como expediente y no tiene número de expediente
        if vals.get('is_expedient') and not self.expedient_number:
            vals['expedient_number'] = self.env['ir.sequence'].next_by_code('sale.order.expedient')
        return super().write(vals)

    # Métodos para estados clickables del statusbar
    def expedient_state_aprobada(self):
        self.write({'expedient_state': 'aprobada'})
        return True

    def expedient_state_rechazada(self):
        self.write({'expedient_state': 'rechazada'})
        return True

    def expedient_state_cancelada(self):
        self.write({'expedient_state': 'cancelada'})
        return True

    def expedient_state_pendiente_documentacion(self):
        self.write({'expedient_state': 'pendiente_documentacion'})
        return True

    # Métodos para cambiar el estado del expediente (mantener para compatibilidad)
    def action_expedient_aprobada(self):
        return self.expedient_state_aprobada()

    def action_expedient_rechazada(self):
        return self.expedient_state_rechazada()

    def action_expedient_cancelada(self):
        return self.expedient_state_cancelada()

    def action_expedient_pendiente_documentacion(self):
        return self.expedient_state_pendiente_documentacion()

    # Métodos para cambiar el estado de devolución
    def action_return_pending(self):
        self.write({'expedient_return_state': 'pending'})
        # Update the latest history record if it exists
        if self.expedient_return_history_ids:
            self.expedient_return_history_ids[0].write({'return_state': 'pending'})
        return True

    def action_return_accepted(self):
        self.write({'expedient_return_state': 'accepted'})
        # Update the latest history record if it exists
        if self.expedient_return_history_ids:
            self.expedient_return_history_ids[0].write({'return_state': 'accepted'})
        return True

    def action_return_rejected(self):
        self.write({'expedient_return_state': 'rejected'})
        # Update the latest history record if it exists
        if self.expedient_return_history_ids:
            self.expedient_return_history_ids[0].write({'return_state': 'rejected'})
        return True

    # Método para registrar la devolución de un expediente
    def register_expedient_return(self):
        self.ensure_one()
        if self.is_expedient:
            # Create a history record when registering a return
            history_vals = {
                'sale_order_id': self.id,
                'return_date': fields.Date.today(),
                'user_id': self.env.user.id,
                'reason': self.expedient_return_reason or 'other',
                'notes': self.expedient_return_notes,
                'return_state': self.expedient_return_state,
            }
            self.env['sale.order.expedient.return.history'].create(history_vals)

            # Update the main expedient records
            if not self.expedient_return_date:
                self.expedient_return_date = fields.Date.today()
            if not self.expedient_return_user_id:
                self.expedient_return_user_id = self.env.user.id
        return True
