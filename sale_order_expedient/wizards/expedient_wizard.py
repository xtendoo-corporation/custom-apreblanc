from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExpedientCreateWizard(models.TransientModel):
    _name = 'expedient.create.wizard'
    _description = 'Wizard to create expedients'

    # Campos básicos
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        default=lambda self: self._get_default_partner()
    )

    expedient_type = fields.Selection([
        ('post_paid', 'Post-pagado'),
        ('pre_paid', 'Pre-pagado'),
    ], string='Tipo de Expediente', default='post_paid', required=True)

    client_id = fields.Char(string='Client ID', required=True)
    expedient_number = fields.Char(string='Expedient Number', required=True)
    partner_readonly = fields.Boolean(string='Partner Readonly', default=False)

    # Plantilla obligatoria
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla',
        domain="[('is_expedient_template', '=', True)]",
        required=True,
        default=lambda self: self._get_default_template()
    )

    @api.model
    def _get_default_partner(self):
        """Obtener partner por defecto desde el contexto o el usuario actual"""
        # Intentar obtener del contexto
        partner_id = self.env.context.get('default_partner_id')
        if partner_id:
            return partner_id

        # Si no hay en contexto, usar la compañía del usuario
        return self.env.company.partner_id.id

    @api.model
    def _get_default_template(self):
        """Obtener plantilla por defecto desde el contexto"""
        return self.env.context.get('default_sale_order_template_id', False)

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Cargar datos de la plantilla"""
        if not self.sale_order_template_id:
            self.partner_readonly = False
            return

        template = self.sale_order_template_id

        # Determinar si debemos cargar el cliente de la plantilla
        if template.partner_id:
            self.partner_id = template.partner_id
            self.partner_readonly = True

    def action_create_expedient(self):
        """Crear expediente"""
        self.ensure_one()

        # Validar que el partner esté configurado
        if not self.partner_id:
            raise ValidationError(_("Debe seleccionar un cliente para el expediente."))

        # Valores comunes para todos los expedientes
        vals = {
            'partner_id': self.partner_id.id,
            'expedient_type': self.expedient_type,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
            'expedient_manager_id': self.env.user.id,
            'sale_order_template_id': self.sale_order_template_id.id,
        }

        # Crear el expediente (sale.order)
        expedient = self.env['sale.order'].create(vals)

        # Aplicar la plantilla: copiar todas las líneas de productos
        if self.sale_order_template_id:
            # Copiar líneas de productos
            for line in self.sale_order_template_id.sale_order_template_line_ids:
                # Obtener datos del producto para el precio
                product = line.product_id

                # Crear línea adaptada a la estructura correcta
                line_vals = {
                    'order_id': expedient.id,
                    'product_id': product.id,
                    'name': line.name or product.name,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom_id.id,
                    # Usar el precio del producto en lugar del de la línea
                    'price_unit': product.list_price,
                    # Solo usar campos que existan
                    'display_type': line.display_type,
                }

                # Añadir descuento solo si el objeto tiene ese atributo
                if hasattr(line, 'discount'):
                    line_vals['discount'] = line.discount

                self.env['sale.order.line'].create(line_vals)

            # Copiar también la nota si existe
            if hasattr(self.sale_order_template_id, 'note') and self.sale_order_template_id.note:
                expedient.note = self.sale_order_template_id.note

            # Verificar si existe payment_term_id antes de intentar acceder
            if hasattr(self.sale_order_template_id, 'payment_term_id') and self.sale_order_template_id.payment_term_id:
                expedient.payment_term_id = self.sale_order_template_id.payment_term_id.id

        # Retornar acción para abrir el expediente creado
        return {
            'name': _('Expediente creado'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': expedient.id,
            'context': {'show_as_expedient': True},
            'target': 'current',
        }

