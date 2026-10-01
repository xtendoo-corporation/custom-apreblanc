# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    template_line_id = fields.Many2one(
        "sale.order.template.line",
        string="Línea de plantilla origen",
        ondelete="set null",
        copy=False,
        help="Línea de la plantilla de presupuesto de la que proviene esta línea. "
        "Permite identificarla de forma estable para no volver a crearla si el "
        "usuario la elimina manualmente del pedido.",
    )

    price_unit_manually_set = fields.Boolean(
        string="Precio fijado manualmente",
        copy=False,
        help="Técnico: indica que el usuario escribió el precio unitario a mano, "
        "para no sobrescribirlo cuando se recalcule el precio al cambiar la "
        "cantidad (price_unit depende de product_uom_qty en el core, así que "
        "cualquier cambio de cantidad recalcula el precio desde la tarifa salvo "
        "que esta protección lo evite).",
    )

    @api.onchange("price_unit")
    def _onchange_price_unit_mark_manually_set(self):
        for line in self:
            line.price_unit_manually_set = True

    @api.onchange("product_id", "product_uom")
    def _onchange_product_reset_manual_price(self):
        for line in self:
            line.price_unit_manually_set = False

    def _compute_price_unit(self):
        """No recalcula el precio de las líneas cuyo precio fue fijado a mano.

        El core recalcula `price_unit` (compute+store+readonly=False) cada vez
        que cambia `product_uom_qty`, sin distinguir si el valor actual lo puso
        el usuario o el propio compute (ver `price_unit_manually_set`). Aquí se
        excluyen esas líneas del recálculo, igual que el core ya hace para
        líneas facturadas (`qty_invoiced > 0`) o de descuento."""
        protected = self.filtered("price_unit_manually_set")
        to_compute = self - protected
        if to_compute:
            super(SaleOrderLine, to_compute)._compute_price_unit()

    def unlink(self):
        """Registra qué líneas de plantilla borró el usuario para no recrearlas.

        Cuando `action_confirm` elimina una línea porque su `application_rule` ya
        no se cumple, marca el contexto `skip_template_exclusion` para no excluirla
        de forma permanente: esa eliminación es una decisión del sistema, no del
        usuario, y la línea debe poder volver a crearse si la regla vuelve a
        cumplirse en una futura reconfirmación.
        """
        if not self.env.context.get("skip_template_exclusion"):
            for line in self:
                if line.template_line_id and line.order_id:
                    line.order_id.excluded_template_line_ids = [
                        fields.Command.link(line.template_line_id.id)
                    ]
        return super().unlink()
