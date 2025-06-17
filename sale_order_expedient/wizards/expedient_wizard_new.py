from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ExpedientWizardNew(models.TransientModel):
    """Wizard para crear expedientes"""
    _name = 'sale.order.expedient.wizard'
    _description = 'Wizard for Expedient Creation'

    # Campos básicos
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    expedient_type = fields.Selection([
        ('post_paid', 'Post-pagado'),
        ('pre_paid', 'Pre-pagado'),
    ], string='Tipo de Expediente', default='post_paid', required=True)
    client_id = fields.Char(string='ID de Cliente', required=True)
    expedient_number = fields.Char(string='Número de Expediente', required=True)
    partner_readonly = fields.Boolean(string='Partner Readonly', default=True)

    # Plantilla obligatoria
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla',
        domain="[('is_expedient_template', '=', True)]",
        required=True
    )

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Actualizar el cliente automáticamente cuando cambia la plantilla"""
        if self.sale_order_template_id and self.sale_order_template_id.partner_id:
            self.partner_id = self.sale_order_template_id.partner_id
            # Opcionalmente, pre-llenar el ID de cliente si existe en el cliente
            if self.partner_id.ref:
                self.client_id = self.partner_id.ref
        else:
            # Si la plantilla no tiene cliente, mostrar un mensaje de error
            return {
                'warning': {
                    'title': 'Error en plantilla',
                    'message': 'La plantilla seleccionada no tiene un cliente asociado. Por favor, seleccione otra plantilla o configure un cliente en la plantilla actual.'
                }
            }

    def action_create_expedient(self):
        """Crear expediente desde el wizard"""
        self.ensure_one()
        
        # Validaciones básicas
        if not self.partner_id:
            raise ValidationError(_("Se requiere un cliente para crear el expediente. La plantilla seleccionada debe tener un cliente asociado."))
        
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
        
        # Implementación mejorada para copiar líneas de la plantilla
        if self.sale_order_template_id:
            # 1. Preparar líneas de productos desde la plantilla
            for line in self.sale_order_template_id.sale_order_template_line_ids:
                # Obtener el producto para acceder a sus datos
                product = line.product_id
                
                # Preparar valores de línea con campos que existen
                order_line_vals = {
                    'order_id': expedient.id,
                    'product_id': product.id,
                    'name': line.name or product.name,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom_id.id,
                    'price_unit': product.list_price,  # Usar precio del producto
                    'display_type': line.display_type,
                }
                
                # Añadir descuento solo si existe
                if hasattr(line, 'discount'):
                    order_line_vals['discount'] = line.discount
                    
                # Crear la línea directamente
                self.env['sale.order.line'].create(order_line_vals)
        
            # 2. Copiar campos adicionales de la plantilla
            if hasattr(self.sale_order_template_id, 'note') and self.sale_order_template_id.note:
                expedient.note = self.sale_order_template_id.note
                
            # 3. Copiar términos de pago si existen
            if hasattr(self.sale_order_template_id, 'payment_term_id') and self.sale_order_template_id.payment_term_id:
                expedient.payment_term_id = self.sale_order_template_id.payment_term_id.id
            
            # 4. Copiar opciones de producto si existen
            if hasattr(self.sale_order_template_id, 'sale_order_template_option_ids'):
                for option in self.sale_order_template_id.sale_order_template_option_ids:
                    option_vals = {
                        'order_id': expedient.id,
                        'product_id': option.product_id.id,
                        'name': option.name,
                        'quantity': option.quantity,
                        'uom_id': option.uom_id.id,
                    }
                    self.env['sale.order.option'].create(option_vals)
    
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
