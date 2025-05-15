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

        # Siempre crear como expediente desde el wizard
        values = {
            'partner_id': self.partner_id.id,
            'is_expedient': True,  # Always set to True when creating from wizard
            'expedient_date': fields.Date.today(),
            'expedient_manager_id': self.env.user.id,
        }

        # Aplicar plantilla si está seleccionada
        if self.sale_order_template_id:
            values['sale_order_template_id'] = self.sale_order_template_id.id

        # Crear el pedido
        new_order = self.env['sale.order'].create(values)

        # Aplicar la plantilla si existe - usando el método correcto en Odoo 17
        if self.sale_order_template_id:
            new_order.with_context(
                default_sale_order_template_id=self.sale_order_template_id.id
            )._onchange_sale_order_template_id()

        # Abrir el formulario del pedido recién creado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': new_order.id,
            'target': 'current',
            'context': {'default_is_expedient': True}
        }

