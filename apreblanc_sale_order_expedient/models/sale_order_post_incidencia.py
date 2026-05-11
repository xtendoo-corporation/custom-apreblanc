from odoo import api, fields, models


class SaleOrderPostIncidencia(models.Model):
    _name = "sale.order.post.incidencia"
    _description = "Post-incidencia de Expediente"
    _order = "fecha_incidencia desc, id desc"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido",
        required=True,
        ondelete="cascade",
        index=True,
    )
    motivo = fields.Char(string="Motivo", required=True)
    fecha_incidencia = fields.Datetime(
        string="Fecha de Incidencia",
        default=fields.Datetime.now,
        required=True,
    )
    responsable_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
    )
    selected = fields.Selection(
        [
            ("apreblac", "Apreblac"),
            ("cliente_estudiar", "Cliente a estudiar"),
        ],
        string="Responsable de la re-revision",
        required=True,
    )
    prioridad = fields.Selection(
        [
            ("baja", "Baja"),
            ("media", "Media"),
            ("alta", "Alta"),
            ("critica", "Critica"),
        ],
        string="Prioridad",
        default="media",
        required=True,
    )
    descripcion_detallada = fields.Text(string="Descripcion Detallada")
    state = fields.Selection(
        [
            ("abierta", "Abierta"),
            ("cerrada", "Cerrada"),
        ],
        string="Estado",
        default="abierta",
        required=True,
    )
    closed_date = fields.Datetime(string="Fecha de Cierre")

    def action_close(self):
        self.write({"state": "cerrada", "closed_date": fields.Datetime.now()})

    def action_reopen(self):
        self.write({"state": "abierta", "closed_date": False})

    def _sync_post_incidencia_flag(self):
        for order in self.mapped("sale_order_id"):
            has_open = bool(
                self.search_count(
                    [
                        ("sale_order_id", "=", order.id),
                        ("state", "=", "abierta"),
                    ]
                )
            )
            order.write({"post_incidencia_activa": has_open})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_post_incidencia_flag()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "state" in vals:
            self._sync_post_incidencia_flag()
        return result

    def unlink(self):
        orders = self.mapped("sale_order_id")
        result = super().unlink()
        for order in orders:
            has_open = bool(
                self.env["sale.order.post.incidencia"].search_count(
                    [
                        ("sale_order_id", "=", order.id),
                        ("state", "=", "abierta"),
                    ]
                )
            )
            order.write({"post_incidencia_activa": has_open})
        return result

