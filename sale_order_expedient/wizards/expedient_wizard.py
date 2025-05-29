from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
        domain=lambda self: self._get_template_domain()
    )

    expedient_number = fields.Char(
        string='Expedient Number',
        required=True,
        help="Expedient number - Unique identifier for this expedient"
    )

    client_id = fields.Char(
        string='Client ID',
        required=True,
        help="Client identifier - primary key field",
    )

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Auto-fill the customer based on the selected template configuration"""
        if self.sale_order_template_id and self.sale_order_template_id.partner_id:
            self.partner_id = self.sale_order_template_id.partner_id

    @api.onchange('expedient_number', 'client_id')
    def _onchange_expedient_client(self):
        """Check if combination of client_id and expedient_number already exists"""
        if self.expedient_number and self.client_id:
            existing = self.env['sale.order'].search([
                ('client_id', '=', self.client_id),
                ('expedient_number', '=', self.expedient_number)
            ], limit=1)
            if existing:
                return {'warning': {
                    'title': _('Duplicate Expedient'),
                    'message': _('An expedient with this Client ID and Expedient Number combination already exists.')
                }}

    def _get_template_domain(self):
        """Get domain for template selection based on user access"""
        return [
            ('active', '=', True),
            '|',
            ('allowed_user_ids', '=', False),
            ('allowed_user_ids', 'in', [self.env.user.id])
        ]

    def action_create_expedient(self):
        self.ensure_one()

        # Check for duplicates before creation
        existing = self.env['sale.order'].search([
            ('client_id', '=', self.client_id),
            ('expedient_number', '=', self.expedient_number)
        ], limit=1)

        if existing:
            raise ValidationError(_("An expedient with this Client ID and Expedient Number combination already exists."))

        # Always create as expedient from the wizard
        values = {
            'partner_id': self.partner_id.id,
            'is_expedient': True,
            'expedient_date': fields.Date.today(),
            'expedient_manager_id': self.env.user.id,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
        }

        # Apply template if selected
        if self.sale_order_template_id:
            values['sale_order_template_id'] = self.sale_order_template_id.id

        # Create the order
        new_order = self.env['sale.order'].create(values)

        # Apply template after creation if template was selected
        if self.sale_order_template_id:
            template = self.sale_order_template_id

            # Apply template data to the order
            template_values = {}
            if hasattr(template, 'note') and template.note:
                template_values['note'] = template.note
            if hasattr(template, 'require_signature') and template.require_signature:
                template_values['require_signature'] = template.require_signature
            if hasattr(template, 'require_payment') and template.require_payment:
                template_values['require_payment'] = template.require_payment
            if hasattr(template, 'validity_days') and template.validity_days:
                template_values['validity_days'] = template.validity_days

            if template_values:
                new_order.write(template_values)

            # Create order lines from template
            if hasattr(template, 'sale_order_template_line_ids'):
                for template_line in template.sale_order_template_line_ids:
                    # Start with the mandatory fields
                    line_values = {
                        'order_id': new_order.id,
                    }

                    # Safely add name - using product name as fallback
                    if hasattr(template_line, 'name') and template_line.name:
                        line_values['name'] = template_line.name
                    elif hasattr(template_line, 'product_id') and template_line.product_id:
                        line_values['name'] = template_line.product_id.name
                    else:
                        line_values['name'] = _("Template Line")

                    # Safely add quantity
                    if hasattr(template_line, 'product_uom_qty'):
                        line_values['product_uom_qty'] = template_line.product_uom_qty
                    else:
                        line_values['product_uom_qty'] = 1.0

                    # Safely add price - omit if not available
                    if hasattr(template_line, 'price_unit'):
                        line_values['price_unit'] = template_line.price_unit

                    # Add product if it exists
                    if hasattr(template_line, 'product_id') and template_line.product_id:
                        line_values['product_id'] = template_line.product_id.id

                        # If no price was found in template, use product price
                        if 'price_unit' not in line_values:
                            line_values['price_unit'] = template_line.product_id.list_price

                    # Add UOM if it exists
                    if hasattr(template_line, 'product_uom_id') and template_line.product_uom_id:
                        line_values['product_uom'] = template_line.product_uom_id.id
                    elif hasattr(template_line, 'product_id') and template_line.product_id.uom_id:
                        line_values['product_uom'] = template_line.product_id.uom_id.id

                    # Add discount if it exists
                    if hasattr(template_line, 'discount'):
                        line_values['discount'] = template_line.discount

                    # Create the order line with all collected values
                    self.env['sale.order.line'].create(line_values)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Expedient'),
            'res_model': 'sale.order',
            'res_id': new_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

