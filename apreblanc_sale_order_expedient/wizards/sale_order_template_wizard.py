from odoo import models, fields, api, _


class SaleOrderTemplateWizard(models.TransientModel):
    _name = "sale.order.template.wizard"
    _description = "Sale Order Template Wizard"

    template_id = fields.Many2one(
        "sale.order.template", string="Quotation Template", required=True
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        domain=[("customer_rank", ">", 0)],
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        """Get default values from the template"""
        defaults = super().default_get(fields_list)

        # Get template from context
        template_id = self.env.context.get("default_template_id")
        if template_id:
            template = self.env["sale.order.template"].browse(template_id)
            defaults["template_id"] = template_id
            if template.partner_id:
                defaults["partner_id"] = template.partner_id.id

        return defaults

    def create_sale_order(self):
        """Create sale order from template with selected customer"""
        self.ensure_one()

        # Create the sale order with the customer from the wizard
        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "sale_order_template_id": self.template_id.id,
        }

        sale_order = self.env["sale.order"].create(sale_order_vals)

        # Apply the template to the sale order
        sale_order._onchange_sale_order_template_id()

        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Order"),
            "res_model": "sale.order",
            "res_id": sale_order.id,
            "view_mode": "form",
            "target": "current",
        }
