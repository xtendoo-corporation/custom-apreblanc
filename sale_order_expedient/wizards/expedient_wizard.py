from odoo import api, fields, models


class ExpedientCreateWizard(models.TransientModel):
    _name = 'expedient.create.wizard'
    _description = 'Wizard to create expedients'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        domain=[('customer_rank', '>', 0)]
    )

    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Quotation Template',
        domain=[('active', '=', True)]
    )

    def action_create_expedient(self):
        self.ensure_one()

        # Always create as expedient from the wizard
        values = {
            'partner_id': self.partner_id.id,
            'is_expedient': True,
            'expedient_date': fields.Date.today(),
            'expedient_manager_id': self.env.user.id,
        }

        # Apply template if selected
        if self.sale_order_template_id:
            values['sale_order_template_id'] = self.sale_order_template_id.id

        # Create the order
        new_order = self.env['sale.order'].create(values)

        # Apply template if exists - using correct method in Odoo 17
        if self.sale_order_template_id:
            new_order.with_context(
                default_sale_order_template_id=self.sale_order_template_id.id
            )._onchange_sale_order_template_id()

        # Open the newly created order form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': new_order.id,
            'target': 'current',
            'context': {'default_is_expedient': True}
        }

