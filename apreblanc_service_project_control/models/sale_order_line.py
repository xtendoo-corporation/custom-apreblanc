from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    apreblanc_start_date = fields.Date(
        string="Fecha inicio",
        help="Fecha planificada de inicio para la tarea creada desde esta línea.",
    )
    apreblanc_target_hours = fields.Float(
        string="Horas objetivo",
        compute="_compute_apreblanc_target_hours",
        store=True,
        readonly=False,
        help="Horas objetivo a usar para crear proyecto y tareas al confirmar el pedido.",
    )

    def _apreblanc_requires_start_date(self):
        self.ensure_one()
        if self.display_type or self.product_template_id.detailed_type != "service":
            return False
        product_name = (self.product_template_id.name or "").strip().lower()
        return product_name in {"primer seguimiento", "segundo seguimiento"}

    @api.constrains("apreblanc_start_date", "product_id", "display_type")
    def _check_apreblanc_start_date_required_for_follow_up(self):
        for line in self:
            if line._apreblanc_requires_start_date() and not line.apreblanc_start_date:
                raise ValidationError(
                    _(
                        "La fecha de inicio es obligatoria para las líneas de producto "
                        "'Primer Seguimiento' y 'Segundo Seguimiento'."
                    )
                )

    @api.depends(
        "product_uom_qty",
        "product_id",
        "display_type",
        "product_template_id.apreblanc_target_hours",
        "product_template_id.apreblanc_create_service_project",
    )
    def _compute_apreblanc_target_hours(self):
        for line in self:
            if line.display_type or not line.product_template_id.apreblanc_create_service_project:
                line.apreblanc_target_hours = 0.0
                continue
            line.apreblanc_target_hours = (
                line.product_uom_qty * line.product_template_id.apreblanc_target_hours
            )
