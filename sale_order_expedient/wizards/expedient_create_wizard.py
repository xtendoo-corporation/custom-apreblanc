from odoo import api, fields, models
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
            # Lógica para crear expediente post-pagado
            # ... existing code ...
            return {'type': 'ir.actions.act_window_close'}
        elif self.expedient_type == 'pre_paid':
            # Lógica para crear expediente pre-pagado
            # ... existing code ...
            return {'type': 'ir.actions.act_window_close'}

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
        # Verificar que hay un expediente prepagado seleccionado
        if not self.pre_paid_expedient_id:
            raise ValidationError(_('Para expedientes prepagados, debe seleccionar un expediente prepagado existente.'))

        # Verificar saldo suficiente
        if self.pre_paid_expedient_id.current_balance < self.amount_total:
            raise ValidationError(_(
                'No hay saldo suficiente en el expediente prepagado. Saldo actual: %.2f, Importe del pedido: %.2f'
            ) % (self.pre_paid_expedient_id.current_balance, self.amount_total))

        # Crear el pedido de venta
        sale_order_vals = {
            'partner_id': self.partner_id.id,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
            'expedient_type': 'pre_paid',
            'expedient_state': 'creada',
            'pre_paid_expedient_id': self.pre_paid_expedient_id.id,
            'expedient_manager_id': self.env.user.id,
            'expedient_date': fields.Date.today(),
        }

        sale_order = self.env['sale.order'].create(sale_order_vals)

        # Agregar líneas desde la plantilla si existe
        if self.sale_order_template_id:
            for template_line in self.sale_order_template_id.sale_order_template_line_ids:
                self.env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'product_id': template_line.product_id.id,
                    'product_uom_qty': template_line.product_uom_qty,
                    'price_unit': template_line.price_unit,
                    'name': template_line.name or template_line.product_id.name,
                })

        # Actualizar saldo del expediente prepagado
        self.pre_paid_expedient_id.current_balance -= self.amount_total

        # Marcar estado como aprobada ya que es pre-pagado
        sale_order.expedient_state = 'aprobada'
        sale_order.message_post(body=_('Expediente pre-pagado aprobado'))

        return sale_order
