from odoo import api, fields, models


class ExpedientCreateWizard(models.TransientModel):
    _name = 'expedient.create.wizard'
    _description = 'Asistente para crear expedientes'

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        domain=[('customer_rank', '>', 0)]
    )

    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla de Presupuesto',
        domain=[('active', '=', True)]
    )

    def action_create_expedient(self):
        self.ensure_one()

        # Crear el expediente
        values = {
            'partner_id': self.partner_id.id,
            'is_expedient': True,
            'expedient_date': fields.Date.today(),
            'expedient_manager_id': self.env.user.id,
        }

        # Aplicar plantilla si está seleccionada
        if self.sale_order_template_id:
            values['sale_order_template_id'] = self.sale_order_template_id.id

        # Crear el expediente
        expedient = self.env['sale.order'].create(values)

        # Aplicar la plantilla si existe - usando el método correcto en Odoo 17
        if self.sale_order_template_id:
            # En Odoo 17 el método es "_onchange_sale_order_template_id"
            expedient.with_context(default_sale_order_template_id=self.sale_order_template_id.id)._onchange_sale_order_template_id()

            # Si el método anterior no existe, intentar esta alternativa
            if hasattr(expedient, '_onchange_template_id'):
                expedient.with_context(default_sale_order_template_id=self.sale_order_template_id.id)._onchange_template_id()

        # Abrir el formulario del expediente recién creado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': expedient.id,
            'target': 'current',
            'context': {'default_is_expedient': True}
        }
