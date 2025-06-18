from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


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

    # Nuevos campos añadidos
    complejidad_proyecto = fields.Selection([
        ('simple', 'Simple'),
        ('complejo', 'Complejo')
    ], string='Complejidad del Proyecto', default='simple',
       help='Indica la complejidad del proyecto del expediente')

    numero_personas = fields.Integer(
        string='Número de Personas',
        help='Número de personas involucradas en el expediente',
        default=1
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
        """Crea un nuevo expediente basado en los datos del formulario"""
        self.ensure_one()

        _logger.info("Iniciando creación de expediente")

        # Preparar los valores para crear el expediente
        expedient_vals = {
            'partner_id': self.partner_id.id,
            'client_id': self.client_id,
            'expedient_number': self.expedient_number,
            'expedient_type': self.expedient_type,
            'expedient_state': 'creada',
            'complejidad_proyecto': self.complejidad_proyecto,
            'numero_personas': self.numero_personas,
            'expedient_start_date': fields.Datetime.now(),
        }

        _logger.info("Valores del expediente: %s", expedient_vals)

        # Verificar si client_id es un campo Many2one o un campo Char
        is_client_id_many2one = self.env['sale.order']._fields.get('client_id').type == 'many2one'
        if is_client_id_many2one and not isinstance(expedient_vals['client_id'], int) and expedient_vals['client_id']:
            _logger.warning("client_id debe ser un ID entero para el campo Many2one")
            try:
                # Intentar convertir a entero si es posible
                expedient_vals['client_id'] = int(expedient_vals['client_id'])
            except (ValueError, TypeError):
                raise UserError(_("El ID de cliente debe ser un número entero"))

        try:
            # Crear expediente con contexto explícito
            ctx = dict(self.env.context, mail_create_nosubscribe=True)
            expedient = self.env['sale.order'].with_context(ctx).create(expedient_vals)

            if not expedient:
                _logger.error("Expediente no creado: el método create no devolvió un objeto")
                raise UserError(_("No se pudo crear el expediente. Contacte con el administrador."))

            _logger.info("Expediente creado con ID: %s", expedient.id)

            # Copiar líneas de productos de la plantilla al expediente
            if self.sale_order_template_id:
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

            # Crear línea inicial en el historial de retornos si es necesario
            if self.env.context.get('create_initial_return', False):
                return_vals = {
                    'sale_order_id': expedient.id,  # Usar el id del expediente creado
                    'name': self.env.context.get('initial_return_description', 'Creación inicial del expediente'),
                    'return_date': fields.Date.today(),
                    'user_id': self.env.user.id,
                }
                self.env['sale.order.expedient.return.history'].create(return_vals)

            # Retornar acción para ver el expediente creado
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': expedient.id,
                'target': 'current',
                'context': {'show_as_expedient': True, 'form_view_initial_mode': 'edit'},
            }
        except Exception as e:
            _logger.exception("Error al crear expediente: %s", str(e))
            raise UserError(_("Error al crear el expediente: %s") % str(e))

