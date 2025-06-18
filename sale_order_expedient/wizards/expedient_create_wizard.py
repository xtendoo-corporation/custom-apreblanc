from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ExpedientCreateWizard(models.TransientModel):
    _name = 'expedient.create.wizard'
    _description = 'Wizard para crear expedientes post-pagados'

    # El tipo de expediente se define por defecto desde el contexto
    expedient_type = fields.Selection([
        ('post_paid', 'Expediente Post-pagado'),
        ('pre_paid', 'Expediente Pre-pagado')
    ], string='Tipo de Expediente Post-pagado', required=True, default=lambda self: self._get_default_expedient_type())

    # Campos básicos
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    client_id = fields.Char(string='Client ID', required=True)
    expedient_number = fields.Char(string='Expedient Number', required=True)
    partner_readonly = fields.Boolean(string='Partner Readonly', default=False)

    # Añadir campo currency_id para resolver el error
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id.id)

    # Campos para plantillas
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla',
        domain="[('is_expedient_template', '=', True)]",
        required=True
    )

    # Campo para el expediente pre-pagado
    pre_paid_expedient_id = fields.Many2one(
        'pre.paid.expedient',
        string='Expediente Prepagado',
        domain="[('partner_id', '=', partner_id), ('state', '=', 'active')]"
    )

    # Campo para el monto total (necesario para validación de saldo)
    amount_total = fields.Monetary(string='Importe Total', currency_field='currency_id')

    @api.model
    def _get_default_expedient_type(self):
        """Obtener el tipo de expediente desde el contexto"""
        return self.env.context.get('default_expedient_type', 'post_paid')

    @api.onchange('expedient_type')
    def _onchange_expedient_type(self):
        """Limpiar campos específicos cuando cambia el tipo de expediente"""
        # Comportamiento silencioso sin ventanas de advertencia
        if self.expedient_type == 'post_paid':
            self.pre_paid_expedient_id = False

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
        """Crear el expediente según el tipo seleccionado"""
        self.ensure_one()

        # Redirigir a la función adecuada según el tipo de expediente
        return self.create_expedient()

    def create_expedient(self):
        """Create expedient based on type"""
        try:
            if self.expedient_type == 'pre_paid':
                # Crear expediente pre-pagado
                sale_order = self._create_pre_paid_expedient()
                # Automáticamente confirmar como pedido de venta
                try:
                    sale_order.action_confirm()
                    sale_order.message_post(body=_('Expediente pre-pagado confirmado automáticamente como pedido de venta'))
                except Exception as e:
                    sale_order.message_post(body=_('Error al confirmar automáticamente el expediente pre-pagado: %s') % str(e))
                    _logger.warning("Error auto-confirming pre-paid expedient: %s", str(e))

                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Expediente Pre-pagado'),
                    'res_model': 'sale.order',
                    'res_id': sale_order.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            else:
                # Crear expediente post-pagado (mantener lógica existente)
                sale_order = self._create_post_paid_expedient()
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Expediente'),
                    'res_model': 'sale.order',
                    'res_id': sale_order.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        except Exception as e:
            _logger.error("Error creating expedient: %s", str(e))
            raise ValidationError(_('Error al crear el expediente: %s') % str(e))

    def _create_pre_paid_expedient(self):
        """Create pre-paid expedient and automatically convert to sale order"""
        # Crear el pedido de venta
        sale_order_vals = {
            'partner_id': self.partner_id.id,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
            'expedient_type': 'pre_paid',
            'expedient_state': 'creada',  # Cambiado de 'aprobada' a 'creada'
            'expedient_manager_id': self.env.user.id,
            'expedient_date_start': fields.Datetime.now(),
            # No establecer fecha fin para estado 'creada'
            'expedient_date_end': False,
            'sale_order_template_id': self.sale_order_template_id.id,
            'state': 'sale',  # Forzar estado sale desde la creación
        }

        # Si se ha seleccionado un expediente pre-pagado, usarlo
        if hasattr(self, 'pre_paid_expedient_id') and self.pre_paid_expedient_id:
            sale_order_vals['pre_paid_expedient_id'] = self.pre_paid_expedient_id.id

        # Crear el pedido
        sale_order = self.env['sale.order'].create(sale_order_vals)

        # Verificar que efectivamente se creó en estado 'sale'
        if sale_order.state != 'sale':
            _logger.warning("Expediente prepagado %s no creado en estado 'sale'. Forzando...", sale_order.name)
            # Usar write con contexto especial en lugar de SQL directo
            sale_order.with_context(force_prepaid_state=True).write({
                'state': 'sale',
                'expedient_state': 'creada',
                'expedient_date_end': False
            })
            # Recargar el registro después de la modificación
            self.env.cache.invalidate()
            sale_order = self.env['sale.order'].browse(sale_order.id)

        # Agregar líneas desde la plantilla
        if self.sale_order_template_id:
            for template_line in self.sale_order_template_id.sale_order_template_line_ids:
                product = template_line.product_id
                line_vals = {
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'name': template_line.name or product.name,
                    'product_uom_qty': template_line.product_uom_qty,
                    'product_uom': template_line.product_uom_id.id,
                    'price_unit': product.list_price,  # Usar precio del producto
                }
                # Añadir campos opcionales solo si existen
                if hasattr(template_line, 'discount'):
                    line_vals['discount'] = template_line.discount
                if hasattr(template_line, 'display_type'):
                    line_vals['display_type'] = template_line.display_type

                self.env['sale.order.line'].create(line_vals)

        # Mensaje explícito sobre el estado
        sale_order.message_post(
            body=_('Expediente pre-pagado creado directamente en estado confirmado (sale) y estado de expediente "creada"'),
            message_type='notification'
        )

        return sale_order

    def _create_post_paid_expedient(self):
        """Create post-paid expedient"""
        # Crear el pedido de venta para expediente post-pagado
        sale_order_vals = {
            'partner_id': self.partner_id.id,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
            'expedient_type': 'post_paid',
            'expedient_state': 'creada',
            'expedient_manager_id': self.env.user.id,
            'expedient_date_start': fields.Datetime.now(),
            'sale_order_template_id': self.sale_order_template_id.id,
        }

        sale_order = self.env['sale.order'].create(sale_order_vals)

        # Agregar líneas desde la plantilla
        if self.sale_order_template_id:
            for template_line in self.sale_order_template_id.sale_order_template_line_ids:
                product = template_line.product_id
                line_vals = {
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'name': template_line.name or product.name,
                    'product_uom_qty': template_line.product_uom_qty,
                    'product_uom': template_line.product_uom_id.id,
                    'price_unit': product.list_price,  # Usar precio del producto
                }
                # Añadir campos opcionales solo si existen
                if hasattr(template_line, 'discount'):
                    line_vals['discount'] = template_line.discount
                if hasattr(template_line, 'display_type'):
                    line_vals['display_type'] = template_line.display_type

                self.env['sale.order.line'].create(line_vals)

        # Copiar también otros datos de la plantilla
        if hasattr(self.sale_order_template_id, 'note') and self.sale_order_template_id.note:
            sale_order.note = self.sale_order_template_id.note

        # Verificar si payment_term_id existe antes de intentar acceder
        if hasattr(self.sale_order_template_id, 'payment_term_id') and self.sale_order_template_id.payment_term_id:
            sale_order.payment_term_id = self.sale_order_template_id.payment_term_id.id

        return sale_order
