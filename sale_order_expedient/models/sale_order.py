from odoo import models, fields, api


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
        readonly=True,
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
        ('draft', 'Borrador'),
        ('in_progress', 'En Progreso'),
        ('pending', 'Pendiente'),
        ('done', 'Completado'),
        ('cancelled', 'Cancelado')
    ], string='Estado del Expediente', default='draft',
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

    # Métodos para cambiar el estado del expediente
    def action_expedient_draft(self):
        self.write({'expedient_state': 'draft'})
        return True
        
    def action_expedient_in_progress(self):
        self.write({'expedient_state': 'in_progress'})
        return True
        
    def action_expedient_pending(self):
        self.write({'expedient_state': 'pending'})
        return True
        
    def action_expedient_done(self):
        self.write({'expedient_state': 'done'})
        return True
        
    def action_expedient_cancelled(self):
        self.write({'expedient_state': 'cancelled'})
        return True
    
    # Métodos para cambiar el estado de devolución
    def action_return_pending(self):
        self.write({'expedient_return_state': 'pending'})
        return True
        
    def action_return_accepted(self):
        self.write({'expedient_return_state': 'accepted'})
        return True
        
    def action_return_rejected(self):
        self.write({'expedient_return_state': 'rejected'})
        return True
    
    # Método para registrar la devolución de un expediente
    def register_expedient_return(self):
        self.ensure_one()
        if self.is_expedient:
            if not self.expedient_return_date:
                self.expedient_return_date = fields.Date.today()
            if not self.expedient_return_user_id:
                self.expedient_return_user_id = self.env.user.id
        return True
