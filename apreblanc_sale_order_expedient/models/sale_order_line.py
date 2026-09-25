# -*- coding: utf-8 -*-

from odoo import fields, models


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
