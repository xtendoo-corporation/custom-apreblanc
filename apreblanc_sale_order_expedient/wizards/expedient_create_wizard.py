from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ExpedientCreateWizard(models.TransientModel):
    _name = "expedient.create.wizard"
    _description = "Wizard para crear expedientes post-pagados"

    person_under_study = fields.Char(
        string="Persona a Estudiar",
        help="Persona que está siendo estudiada en el expediente",
    )

    show_warning_message = fields.Boolean(
        string="Mostrar Mensaje de Advertencia",
        compute="_compute_show_warning_message",
        default=False,
        help="Indica si se debe mostrar un mensaje de advertencia al crear el expediente",
    )
    show_warning_text_person = fields.Boolean(
        string="Advertencia Persona",
        compute="_compute_show_warning_message",
        default=False,
        help="Indica si ya existe un expediente con la misma persona a estudiar",
    )

    show_warning_text_client = fields.Boolean(
        string="Advertencia Cliente",
        compute="_compute_show_warning_message",
        default=False,
        help="Indica si ya existe un expediente con el mismo ID de cliente",
    )
    show_warning_text_numberexp = fields.Boolean(
        string="Advertencia Número Expediente",
        compute="_compute_show_warning_message",
        default=False,
        help="Indica si ya existe un expediente con el mismo número de expediente",
    )

    # El tipo de expediente se define por defecto desde el contexto
    expedient_type = fields.Selection(
        [
            ("post_paid", "Expediente Post-pagado"),
            ("pre_paid", "Expediente Pre-pagado"),
        ],
        string="Tipo de Expediente Post-pagado",
        required=True,
        default=lambda self: self._get_default_expedient_type(),
    )

    # Campos básicos
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    client_id = fields.Char(string="Client ID", required=True)
    expedient_number = fields.Char(string="Expedient Number", required=True)
    partner_readonly = fields.Boolean(string="Partner Readonly", default=False)
    sub_cartera_id = fields.Many2one(
        "res.partner",
        string="Sub cartera",
    )

    # Campos faltantes que aparecen en la vista
    expedient_date = fields.Date(string="Fecha de Expediente")
    expedient_manager_id = fields.Many2one("res.users", string="Responsable")

    # Campos para plantillas
    sale_order_template_id = fields.Many2one(
        "sale.order.template", string="Plantilla", required=True
    )

    # Campo para el expediente pre-pagado
    pre_paid_expedient_id = fields.Many2one(
        "pre.paid.expedient",
        string="Expediente Prepagado",
        domain="[('partner_id', '=', partner_id), ('state', '=', 'active')]",
    )

    # Campo para el monto total (necesario para validación de saldo)
    amount_total = fields.Monetary(string="Importe Total", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id.id,
    )

    @api.model
    def _get_default_expedient_type(self):
        """Obtener el tipo de expediente desde el contexto"""
        return self.env.context.get("default_expedient_type", "post_paid")

    @api.onchange("expedient_type")
    def _onchange_expedient_type(self):
        """Limpiar campos específicos cuando cambia el tipo de expediente"""
        # Comportamiento silencioso sin ventanas de advertencia
        if self.expedient_type == "post_paid":
            self.pre_paid_expedient_id = False

    @api.onchange("sale_order_template_id")
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
        if template.sub_cartera_id:
            self.sub_cartera_id = template.sub_cartera_id.id

    def action_create_expedient(self):
        """Crear el expediente según el tipo seleccionado"""
        self.ensure_one()

        # Redirigir a la función adecuada según el tipo de expediente
        return self.create_expedient()

    def create_expedient(self):
        """Create expedient based on type"""
        try:
            if self.expedient_type == "pre_paid":
                # Crear expediente pre-pagado
                sale_order = self._create_pre_paid_expedient()
                # Automáticamente confirmar como pedido de venta
                try:
                    sale_order.action_confirm()
                    sale_order.message_post(
                        body=_(
                            "Expediente pre-pagado confirmado automáticamente como pedido de venta"
                        )
                    )
                except Exception as e:
                    sale_order.message_post(
                        body=_(
                            "Error al confirmar automáticamente el expediente pre-pagado: %s"
                        )
                        % str(e)
                    )
                    _logger.warning(
                        "Error auto-confirming pre-paid expedient: %s", str(e)
                    )

                return {
                    "type": "ir.actions.act_window",
                    "name": _("Expediente Pre-pagado"),
                    "res_model": "sale.order",
                    "res_id": sale_order.id,
                    "view_mode": "form",
                    "view_id": self.env.ref(
                        "apreblanc_sale_order_expedient.view_order_form_expedient"
                    ).id,
                    "target": "current",
                    "context": {"show_as_expedient": True},
                }
            else:
                # Crear expediente post-pagado (mantener lógica existente)
                sale_order = self._create_post_paid_expedient()
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Expediente"),
                    "res_model": "sale.order",
                    "res_id": sale_order.id,
                    "view_mode": "form",
                    "view_id": self.env.ref(
                        "apreblanc_sale_order_expedient.view_order_form_expedient"
                    ).id,
                    "target": "current",
                    "context": {"show_as_expedient": True},
                }
        except Exception as e:
            _logger.error("Error creating expedient: %s", str(e))
            raise ValidationError(_("Error al crear el expediente: %s") % str(e))

    def _create_pre_paid_expedient(self):
        """Create pre-paid expedient and automatically convert to sale order"""
        # Obtener la secuencia PRE directamente según el tipo de expediente
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "sale.order.pre")], limit=1
        )
        sequence_number = False
        if sequence:
            sequence_number = sequence.next_by_id()

        # Crear el pedido de venta
        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "client_id": self.client_id,
            "expedient_number": self.expedient_number,
            "expedient_type": "pre_paid",
            "expedient_state": "creada",  # Cambiado de 'aprobada' a 'creada'
            "expedient_manager_id": self.env.user.id,
            "expedient_date_start": fields.Datetime.now(),
            # No establecer fecha fin para estado 'creada'
            "expedient_date_end": False,
            "sale_order_template_id": self.sale_order_template_id.id,
            "sub_cartera_id": (
                self.sale_order_template_id.sub_cartera_id.id
                if self.sale_order_template_id
                else False
            ),
            "state": "sale",  # Forzar estado sale desde la creación
            "person_under_study": self.person_under_study,  # Transferir el campo studied_person
            "person_type": False,
            "expedient_difficulty": False,
            "deadline": False,
            "type_id": 3,
        }

        # Si hay una secuencia configurada, agregar el nombre
        if sequence_number:
            sale_order_vals["name"] = sequence_number

        # Si se ha seleccionado un expediente pre-pagado, usarlo
        if hasattr(self, "pre_paid_expedient_id") and self.pre_paid_expedient_id:
            sale_order_vals["pre_paid_expedient_id"] = self.pre_paid_expedient_id.id

        # Crear el pedido
        sale_order = self.env["sale.order"].create(sale_order_vals)

        # Verificar que efectivamente se creó en estado 'sale'
        if sale_order.state != "sale":
            _logger.warning(
                "Expediente prepagado %s no creado en estado 'sale'. Forzando...",
                sale_order.name,
            )
            # Usar write con contexto especial en lugar de SQL directo
            sale_order.with_context(force_prepaid_state=True).write(
                {
                    "state": "sale",
                    "expedient_state": "creada",
                    "expedient_date_end": False,
                }
            )
            # Recargar el registro después de la modificación
            self.env.cache.invalidate()
            sale_order = self.env["sale.order"].browse(sale_order.id)

        # Agregar líneas desde la plantilla
        if self.sale_order_template_id:
            for (
                template_line
            ) in self.sale_order_template_id.sale_order_template_line_ids:
                # NO filtrar aquí por _should_apply - se hará al confirmar
                # cuando expedient_difficulty y otros campos ya tengan valor
                product = template_line.product_id
                line_vals = {
                    "order_id": sale_order.id,
                    "product_id": product.id,
                    "name": template_line.name or product.name,
                    "product_uom_qty": template_line.product_uom_qty,
                    "product_uom": template_line.product_uom_id.id,
                    "price_unit": product.list_price,
                }
                # Añadir campos opcionales solo si existen
                if hasattr(template_line, "discount"):
                    line_vals["discount"] = template_line.discount
                if hasattr(template_line, "display_type"):
                    line_vals["display_type"] = template_line.display_type

                self.env["sale.order.line"].create(line_vals)

        # Mensaje explícito sobre el estado
        sale_order.message_post(
            body=_(
                'Expediente pre-pagado creado directamente en estado confirmado (sale) y estado de expediente "creada"'
            ),
            message_type="notification",
        )

        return sale_order

    def _create_post_paid_expedient(self):
        """Create post-paid expedient"""
        # Obtener la secuencia POST directamente según el tipo de expediente
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "sale.order.post")], limit=1
        )
        sequence_number = False
        if sequence:
            sequence_number = sequence.next_by_id()

        # Crear el pedido de venta para expediente post-pagado
        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "client_id": self.client_id,
            "expedient_number": self.expedient_number,
            "expedient_type": "post_paid",
            "expedient_state": "creada",
            "expedient_manager_id": self.env.user.id,
            "expedient_date_start": fields.Datetime.now(),
            "sale_order_template_id": self.sale_order_template_id.id,
            "sub_cartera_id": (
                self.sale_order_template_id.sub_cartera_id.id
                if self.sale_order_template_id
                else False
            ),
            "person_under_study": self.person_under_study,  # Transferir el campo studied_person
            "person_type": False,
            "expedient_difficulty": False,
            "deadline": False,
            "type_id": 2,
        }

        # Si hay una secuencia configurada, agregar el nombre
        if sequence_number:
            sale_order_vals["name"] = sequence_number

        sale_order = self.env["sale.order"].create(sale_order_vals)

        # Agregar líneas desde la plantilla
        if self.sale_order_template_id:
            for (
                template_line
            ) in self.sale_order_template_id.sale_order_template_line_ids:
                # NO filtrar aquí por _should_apply - se hará al confirmar
                # cuando expedient_difficulty y otros campos ya tengan valor
                product = template_line.product_id
                line_vals = {
                    "order_id": sale_order.id,
                    "product_id": product.id,
                    "name": template_line.name or product.name,
                    "product_uom_qty": template_line.product_uom_qty,
                    "product_uom": template_line.product_uom_id.id,
                    "price_unit": product.list_price,
                }
                # Añadir campos opcionales solo si existen
                if hasattr(template_line, "discount"):
                    line_vals["discount"] = template_line.discount
                if hasattr(template_line, "display_type"):
                    line_vals["display_type"] = template_line.display_type

                self.env["sale.order.line"].create(line_vals)

        # Copiar también otros datos de la plantilla
        if (
            hasattr(self.sale_order_template_id, "note")
            and self.sale_order_template_id.note
        ):
            sale_order.note = self.sale_order_template_id.note

        # Verificar si payment_term_id existe antes de intentar acceder
        if (
            hasattr(self.sale_order_template_id, "payment_term_id")
            and self.sale_order_template_id.payment_term_id
        ):
            sale_order.payment_term_id = self.sale_order_template_id.payment_term_id.id

        return sale_order

    @api.depends("person_under_study", "client_id", "expedient_number")
    def _compute_show_warning_message(self):
        for record in self:
            # Inicializar todos los campos de advertencia en False
            record.show_warning_text_person = False
            record.show_warning_text_client = False
            record.show_warning_text_numberexp = False
            record.show_warning_message = False

            # Buscar expedientes existentes con la misma persona bajo estudio si el campo tiene valor
            if record.person_under_study:
                existing_orders_study = self.env["sale.order"].search(
                    [("person_under_study", "=", record.person_under_study)]
                )
                if existing_orders_study:
                    record.show_warning_text_person = True

            # Buscar expedientes existentes con el mismo número de expediente si el campo tiene valor
            if record.expedient_number:
                existing_orders_number = self.env["sale.order"].search(
                    [("expedient_number", "=", record.expedient_number)]
                )
                if existing_orders_number:
                    record.show_warning_text_numberexp = True

            # Buscar expedientes existentes con el mismo ID de cliente si el campo tiene valor
            if record.client_id:
                existing_orders_client = self.env["sale.order"].search(
                    [
                        ("client_id", "=", record.client_id),
                    ]
                )
                if existing_orders_client:
                    record.show_warning_text_client = True

            # Establecer show_warning_message en True si cualquiera de los campos de advertencia es True
            record.show_warning_message = (
                record.show_warning_text_numberexp
                or record.show_warning_text_person
                or record.show_warning_text_client
            )
