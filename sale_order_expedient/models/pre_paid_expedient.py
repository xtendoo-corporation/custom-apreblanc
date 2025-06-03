from odoo import api, fields, models, _, exceptions


class PrePaidExpedient(models.Model):
    _name = 'pre.paid.expedient'
    _description = 'Expediente Prepagado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name desc"
    _sql_constraints = [
        ('client_expedient_unique',
         'unique(client_id, expedient_number)',
         'La combinación de ID de Cliente y Número de Expediente debe ser única!')
    ]

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    expedient_number = fields.Char(
        string='Número de Expediente',
        copy=False,
        index=True,
        required=True,
        help="Identificador del expediente - debe ser único cuando se combina con ID de Cliente"
    )
    client_id = fields.Char(
        string='ID de Cliente',
        copy=False,
        index=True,
        required=True,
        help="Identificador del cliente - parte de la clave primaria junto con el Número de Expediente"
    )
    expedient_date = fields.Date(
        string='Fecha de Inicio',
        default=fields.Date.context_today,
        help='Fecha de inicio del expediente',
        tracking=True,
    )
    expedient_deadline = fields.Date(
        string='Fecha Límite',
        help='Fecha límite para completar el expediente',
        tracking=True,
    )
    expedient_manager_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
        help='Usuario responsable de gestionar este expediente',
    )
    expedient_state = fields.Selection([
        ('creada', 'Creado'),
        ('pendiente_documentacion', 'Pendiente de Documentación'),
        ('aprobada', 'Aprobado'),
        ('rechazada', 'Rechazado'),
        ('cancelada', 'Cancelado')
    ], string="Estado", default='creada', tracking=True,
        help="Estado actual del expediente prepagado")

    expedient_notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre este expediente',
        tracking=True,
    )

    # Campos específicos para expedientes prepagados
    initial_balance = fields.Float(
        string='Saldo Inicial',
        default=0.0,
        help='Saldo inicial del expediente prepagado',
        tracking=True,
    )
    current_balance = fields.Float(
        string='Saldo Actual',
        compute='_compute_current_balance',
        store=True,
        help='Saldo actual disponible',
    )

    # Relaciones con pedidos de venta
    sale_order_ids = fields.One2many(
        'sale.order',
        'pre_paid_expedient_id',
        string='Pedidos de Venta',
        help='Pedidos asociados a este expediente prepagado',
    )

    # Relación con facturas
    invoice_ids = fields.One2many(
        'account.move',
        'pre_paid_expedient_id',
        string='Facturas',
        help='Facturas generadas para este expediente prepagado',
        domain=[('move_type', '=', 'out_invoice')]
    )

    # Relación con asientos contables
    account_move_ids = fields.One2many(
        'account.move',
        'pre_paid_expedient_id',
        string='Asientos Contables',
        help='Asientos contables generados para este expediente prepagado',
        domain=[('move_type', '=', 'entry')]
    )

    invoice_count = fields.Integer(
        string="Número de Facturas",
        compute="_compute_invoice_count",
        store=True
    )

    account_move_count = fields.Integer(
        string="Número de Asientos",
        compute="_compute_account_move_count",
        store=True
    )

    # Información del cliente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
    )
    partner_vat = fields.Char(related='partner_id.vat', string='NIF/CIF', readonly=True)
    partner_phone = fields.Char(related='partner_id.phone', string='Teléfono', readonly=True)
    partner_email = fields.Char(related='partner_id.email', string='Email', readonly=True)

    # Añadir el siguiente campo en el modelo pre.paid.expedient
    expedient_return_history_ids = fields.One2many(
        "pre.paid.expedient.return.history",
        "pre_paid_expedient_id",
        string="Historial de Devoluciones"
    )
    return_count = fields.Integer(
        string="Número de Devoluciones",
        compute="_compute_return_count",
        store=True
    )

    # Añadir campo para la plantilla de venta
    sale_order_template_id = fields.Many2one(
        'sale.order.template',
        string='Plantilla de Venta',
        help='Plantilla usada para crear este expediente prepagado',
    )

    @api.depends('expedient_number', 'client_id')
    def _compute_name(self):
        for record in self:
            record.name = f"EP/{record.client_id}/{record.expedient_number}" if record.client_id and record.expedient_number else "Nuevo Expediente Prepagado"

    @api.depends('initial_balance', 'sale_order_ids.amount_total', 'sale_order_ids.state')
    def _compute_current_balance(self):
        for record in self:
            consumed = sum(order.amount_total for order in record.sale_order_ids if order.state in ('sale', 'done'))
            record.current_balance = record.initial_balance - consumed

    @api.depends("expedient_return_history_ids")
    def _compute_return_count(self):
        for record in self:
            record.return_count = len(record.expedient_return_history_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids.filtered(lambda i: i.move_type == 'out_invoice'))

    @api.depends('account_move_ids')
    def _compute_account_move_count(self):
        for record in self:
            record.account_move_count = len(record.account_move_ids.filtered(lambda m: m.move_type == 'entry'))

    @api.model_create_multi
    def create(self, vals_list):
        expedients = super().create(vals_list)
        # Generar solamente la factura automáticamente para cada expediente creado
        for expedient in expedients:
            expedient._create_invoice()
            # Se elimina la llamada a _create_accounting_entry()
        return expedients

    def _create_invoice(self):
        """Crear factura para el expediente prepagado usando líneas de la plantilla si existe"""
        self.ensure_one()

        # Crear la factura con valores básicos
        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
            'narration': _('Factura generada automáticamente para el expediente prepagado %s') % self.name,
            'pre_paid_expedient_id': self.id,
            'invoice_line_ids': [],
        }

        # Si hay una plantilla, usar sus líneas
        if self.sale_order_template_id and self.sale_order_template_id.sale_order_template_line_ids:
            total_amount = 0.0

            # Agregar líneas de la plantilla
            for template_line in self.sale_order_template_id.sale_order_template_line_ids:
                product = template_line.product_id if hasattr(template_line, 'product_id') else False

                # Determinar la cuenta contable para esta línea
                account = False
                if product and hasattr(product, 'property_account_income_id') and product.property_account_income_id:
                    account = product.property_account_income_id
                elif product and hasattr(product, 'categ_id') and hasattr(product.categ_id, 'property_account_income_categ_id') and product.categ_id.property_account_income_categ_id:
                    account = product.categ_id.property_account_income_categ_id
                else:
                    # Buscar una cuenta de ingresos por defecto
                    account = self.env['account.account'].search([
                        ('company_id', '=', self.env.company.id),
                        ('account_type', '=', 'income')
                    ], limit=1)

                if not account:
                    self.message_post(
                        body=_('No se pudo determinar la cuenta contable para el producto %s') %
                            (product.name if product else (template_line.name if hasattr(template_line, 'name') else "Desconocido")),
                        subtype_xmlid='mail.mt_note'
                    )
                    continue

                # Obtener precio y cantidad verificando los nombres de campo disponibles
                price = 0.0
                qty = 1.0
                discount = 0.0

                # Verificar campo para precio
                if hasattr(template_line, 'price_unit'):
                    price = template_line.price_unit
                elif product:
                    price = product.list_price

                # Verificar campo para cantidad
                if hasattr(template_line, 'product_uom_qty'):
                    qty = template_line.product_uom_qty

                # Verificar campo para descuento
                if hasattr(template_line, 'discount'):
                    discount = template_line.discount

                # Valores para la línea de factura
                line_vals = {
                    'name': template_line.name if hasattr(template_line, 'name') else (product.name if product else "Línea de plantilla"),
                    'product_id': product.id if product else False,
                    'price_unit': price,
                    'quantity': qty,
                    'discount': discount,
                    'account_id': account.id,
                }

                # Añadir UOM si está disponible
                if hasattr(template_line, 'product_uom_id') and template_line.product_uom_id:
                    line_vals['product_uom_id'] = template_line.product_uom_id.id
                elif product and hasattr(product, 'uom_id') and product.uom_id:
                    line_vals['product_uom_id'] = product.uom_id.id

                # Añadir la línea a la factura
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

                # Acumular el importe total
                line_amount = price * qty * (1 - (discount / 100.0))
                total_amount += line_amount

            # Actualizar el saldo inicial del expediente con el total calculado
            if total_amount > 0 and self.initial_balance == 0:
                self.write({'initial_balance': total_amount})
        else:
            # Si no hay plantilla, crear una línea genérica
            invoice_vals['invoice_line_ids'] = [(0, 0, {
                'name': _('Expediente Prepagado %s') % self.name,
                'quantity': 1,
                'price_unit': self.initial_balance,
            })]

        # Crear la factura
        invoice = self.env['account.move'].create(invoice_vals)

        # Confirmar (publicar) la factura automáticamente
        try:
            invoice.action_post()
            self.message_post(
                body=_('Factura %s creada y confirmada automáticamente') % invoice.name,
                subtype_xmlid='mail.mt_note'
            )
        except Exception as e:
            self.message_post(
                body=_('Factura %s creada pero no se pudo confirmar: %s') % (invoice.name, str(e)),
                subtype_xmlid='mail.mt_note'
            )

        return invoice

    # Mantener el método pero vacío para evitar errores en código existente
    def _create_accounting_entry(self):
        """Este método ya no crea asientos contables"""
        return False

    def action_view_invoices(self):
        """Acción para ver las facturas relacionadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids), ('move_type', '=', 'out_invoice')],
            'context': {'default_pre_paid_expedient_id': self.id},
        }

    def action_view_account_moves(self):
        """Acción para ver los asientos contables relacionados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asientos Contables'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.account_move_ids.ids), ('move_type', '=', 'entry')],
            'context': {'default_pre_paid_expedient_id': self.id},
        }

    # Añadir métodos para cambiar estados
    def action_expedient_aprobada(self):
        self.ensure_one()
        self.write({'expedient_state': 'aprobada'})
        return True

    def action_expedient_rechazada(self):
        self.ensure_one()
        self.write({'expedient_state': 'rechazada'})
        return True

    def action_expedient_cancelada(self):
        self.ensure_one()
        self.write({'expedient_state': 'cancelada'})
        return True

    def action_expedient_pendiente_documentacion(self):
        self.ensure_one()
        self.write({'expedient_state': 'pendiente_documentacion'})
        return True
