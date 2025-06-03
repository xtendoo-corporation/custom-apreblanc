from odoo import api, fields, models

class ExpedientCreateWizard(models.TransientModel):
    _name = 'expedient.create.wizard'
    _description = 'Wizard para crear expedientes'

    # El tipo de expediente se define por defecto desde el contexto
    expedient_type = fields.Selection([
        ('post_paid', 'Expediente Postpago'),
        ('pre_paid', 'Expediente Prepagado')
    ], string='Tipo de Expediente', required=True, default=lambda self: self._get_default_expedient_type())

    # ... existing code ...

    @api.model
    def _get_default_expedient_type(self):
        """Obtener el tipo de expediente desde el contexto"""
        return self.env.context.get('default_expedient_type', 'post_paid')

    # ... existing code ...

    @api.onchange('expedient_type')
    def _onchange_expedient_type(self):
        """Limpiar campos específicos cuando cambia el tipo de expediente"""
        # Este método podría ya no ser necesario si el tipo no cambia,
        # pero lo dejamos por compatibilidad
        if self.expedient_type == 'post_paid':
            # Limpiar campos específicos de prepago
            pass
        elif self.expedient_type == 'pre_paid':
            # Limpiar campos específicos de postpago
            pass

    # ... existing code ...

    def action_create_expedient(self):
        """Crear el expediente según el tipo seleccionado"""
        self.ensure_one()
        if self.expedient_type == 'post_paid':
            # Lógica para crear expediente postpago
            # ... existing code ...
            return {'type': 'ir.actions.act_window_close'}
        elif self.expedient_type == 'pre_paid':
            # Lógica para crear expediente prepagado
            # ... existing code ...
            return {'type': 'ir.actions.act_window_close'}
