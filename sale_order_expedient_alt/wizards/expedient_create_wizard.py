from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ExpedientCreateWizard(models.TransientModel):
    _name = "expedient.create.wizard"
    _description = "Wizard para crear expedientes"

    # Tipo de expediente
    expedient_payment_type = fields.Selection([
        ('post_paid', 'Expediente Postpagado'),
        ('pre_paid', 'Expediente Prepagado')
    ], string="Tipo de Expediente", required=True, default='post_paid')

    # Campos básicos
    partner_id = fields.Many2one(
        "res.partner", string="Cliente", required=True,
        domain=[('customer_rank', '>', 0)]
    )
    client_id = fields.Many2one(
        "res.partner", string="Cliente de Referencia"
    )
    expedient_number = fields.Char(string="Número de Expediente", required=True)

    # Añadir los campos faltantes
    expedient_date = fields.Date(string="Fecha de Expediente", default=fields.Date.today)
    expedient_deadline = fields.Date(string="Fecha Límite")

    # Añadimos este campo para asegurar que se filtre por el usuario actual
    expedient_manager_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        required=True
    )

    # Campos adicionales
    expedient_notes = fields.Text(string="Notas")
    sale_order_template_id = fields.Many2one(
        "sale.order.template",
        string="Plantilla",
        domain=lambda self: [
            '|', ('allowed_user_ids', '=', self.env.user.id),
            ('allowed_user_ids', '=', False)
        ]
    )

    @api.onchange('sale_order_template_id')
    def onchange_sale_order_template_id(self):
        if self.sale_order_template_id:
            self.partner_id = self.sale_order_template_id.partner_id

    def action_create_expedient(self):
        self.ensure_one()

        # Valores comunes para ambos tipos de expedientes
        common_values = {
            'partner_id': self.partner_id.id,
            'client_id': self.client_id.id if self.client_id else False,
            'expedient_number': self.expedient_number,
            'expedient_date': self.expedient_date,
            'expedient_deadline': self.expedient_deadline,
            'expedient_manager_id': self.expedient_manager_id.id,
            'expedient_notes': self.expedient_notes,
            'expedient_state': 'creada',
        }

        if self.expedient_payment_type == 'pre_paid':
            # Crear expediente prepagado
            pre_paid_expedient = self.env['pre.paid.expedient'].create(common_values)

            # Retornar acción para abrir el nuevo expediente prepagado
            return {
                'name': 'Expediente Prepagado',
                'type': 'ir.actions.act_window',
                'res_model': 'pre.paid.expedient',
                'res_id': pre_paid_expedient.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Crear expediente postpagado (pedido de venta)
            values = common_values.copy()
            values.update({
                'expedient_type': 'post_paid',
                'user_id': self.expedient_manager_id.id,
                'date_order': self.expedient_date,
                'validity_date': self.expedient_deadline,
            })

            # Si hay plantilla, utilizar sus valores
            if self.sale_order_template_id:
                template = self.sale_order_template_id.with_context(lang=self.partner_id.lang)
                values.update({
                    'note': template.note or '',
                    'terms_type': template.terms_type,
                    'terms_id': template.terms_id.id,
                    'pricelist_id': self.env['product.pricelist'].search([('partner_id', '=', self.partner_id.id)], limit=1).id or self.env['product.pricelist'].search([], limit=1).id,
                    'payment_term_id': self.partner_id.property_payment_term_id.id or False,
                })

                sale_order = self.env['sale.order'].create(values)

                # Copiar líneas de la plantilla
                for line in template.sale_order_template_line_ids:
                    sale_order.order_line.create({
                        'order_id': sale_order.id,
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom_id.id,
                        'price_unit': line.price_unit,
                        'discount': line.discount,
                    })
            else:
                sale_order = self.env['sale.order'].create(values)

            # Retornar acción para abrir el nuevo pedido de venta (expediente postpagado)
            return {
                'name': 'Expediente Postpagado',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
                'target': 'current',
            }
