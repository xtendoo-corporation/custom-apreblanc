from odoo import models, fields, api


class PostIncidenciaWizard(models.TransientModel):
    _name = 'post.incidencia.wizard'
    _description = 'Wizard para Post-incidencia'

    expedient_id = fields.Many2one('sale.order', string='Expediente', required=True)
    motivo = fields.Char(string='Motivo', required=True)
    fecha_incidencia = fields.Datetime(string='Fecha de Incidencia', default=fields.Datetime.now, required=True)
    responsable_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)
    prioridad = fields.Selection([
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica')
    ], string='Prioridad', default='media', required=True)
    descripcion_detallada = fields.Text(string='Descripción Detallada')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['expedient_id'] = self.env.context['active_id']
        return res

    def action_confirm_post_incidencia(self):
        # Usar el metodo específico que no intercepta
        self.expedient_id.sudo().write({'expedient_state': 'post_incidencia'})
        return {'type': 'ir.actions.act_window_close'}


        return {'type': 'ir.actions.act_window_close'}
