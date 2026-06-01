# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.osv import expression


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    @api.model
    def _resolve_template_pricelist_id(self, partner_id=False, sub_cartera_id=False):
        """Prioriza subcartera, luego partner y finalmente la tarifa por defecto de Odoo."""
        partner = (
            self.env["res.partner"].browse(partner_id).with_company(self.env.company)
            if partner_id
            else self.env["res.partner"]
        )
        sub_cartera = (
            self.env["res.partner"].browse(sub_cartera_id).with_company(self.env.company)
            if sub_cartera_id
            else self.env["res.partner"]
        )

        if sub_cartera and sub_cartera.property_product_pricelist:
            return sub_cartera.property_product_pricelist.id
        if partner and partner.property_product_pricelist:
            return partner.property_product_pricelist.id

        sale_order = self.env["sale.order"].new(
            {"partner_id": partner.id} if partner else {}
        )
        return sale_order.pricelist_id.id or False

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        help="Default customer for this quotation template",
    )
    sub_cartera_id = fields.Many2one(
        "res.partner",
        string="Sub cartera",
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Tarifa",
        help="Tarifa de precios que se aplica a los pedidos creados con esta plantilla. "
             "Si hay subcartera, se usa la tarifa de la subcartera.",
    )
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "sale_template_groups_rel",
        "template_id",
        "group_id",
        string="Allowed Groups",
        help="If groups are selected, only users belonging to these groups will be able to use this template.",
    )
    can_use_template = fields.Boolean(
        string="Can Use Template",
        compute="_compute_can_use_template",
        help="Indicates if the current user can use this template",
    )
    is_restricted = fields.Boolean(
        string="Restringida",
        compute="_compute_is_restricted",
        store=True,
        help="Indicates if this template is restricted to certain groups",
    )

    @api.onchange("partner_id", "sub_cartera_id")
    def _onchange_partner_or_sub_cartera_id(self):
        """Sincroniza la tarifa con prioridad subcartera y fallback al partner."""
        for template in self:
            template.pricelist_id = template._resolve_template_pricelist_id(
                partner_id=template.partner_id.id,
                sub_cartera_id=template.sub_cartera_id.id,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("pricelist_id"):
                vals["pricelist_id"] = self._resolve_template_pricelist_id(
                    partner_id=vals.get("partner_id"),
                    sub_cartera_id=vals.get("sub_cartera_id"),
                )
        return super().create(vals_list)

    def write(self, vals):
        if not vals.get("pricelist_id") and (
            "partner_id" in vals or "sub_cartera_id" in vals
        ):
            if len(self) > 1:
                results = []
                for template in self:
                    template_vals = dict(vals)
                    template_vals["pricelist_id"] = template._resolve_template_pricelist_id(
                        partner_id=template_vals.get("partner_id", template.partner_id.id),
                        sub_cartera_id=template_vals.get(
                            "sub_cartera_id", template.sub_cartera_id.id
                        ),
                    )
                    results.append(super(SaleOrderTemplate, template).write(template_vals))
                return all(results)

            vals = dict(vals)
            vals["pricelist_id"] = self._resolve_template_pricelist_id(
                partner_id=vals.get("partner_id", self.partner_id.id),
                sub_cartera_id=vals.get("sub_cartera_id", self.sub_cartera_id.id),
            )
        return super().write(vals)

    @api.depends("allowed_group_ids")
    def _compute_can_use_template(self):
        """Determine if the current user can use this template based on groups"""
        current_user = self.env.user
        for template in self:
            if not template.allowed_group_ids:
                template.can_use_template = True
                continue

            # Check if the user belongs to any of the assigned groups
            user_groups = current_user.groups_id
            template.can_use_template = bool(
                set(template.allowed_group_ids.ids) & set(user_groups.ids)
            )

    @api.depends("allowed_group_ids")
    def _compute_is_restricted(self):
        """Calculates if the template is restricted based on assigned groups"""
        for template in self:
            template.is_restricted = bool(template.allowed_group_ids)

    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        """Sobrescribe _search para forzar el filtrado por grupos autorizados"""
        # Verificar si el usuario es administrador (tiene acceso a Ajustes)
        current_user = self.env.user
        is_admin = current_user.has_group("base.group_system")

        # Los administradores pueden ver todas las plantillas
        if is_admin:
            return super()._search(
                domain,
                offset=offset,
                limit=limit,
                order=order,
                access_rights_uid=access_rights_uid,
            )

        # Para usuarios normales, aplicar filtro por grupos permitidos
        user_groups_ids = current_user.groups_id.ids

        # Crear un dominio que filtre según grupos permitidos
        # 1. Plantillas sin grupos asignados (accesibles para todos)
        # 2. O plantillas donde el usuario pertenece a algún grupo permitido
        group_domain = [
            "|",
            (
                "allowed_group_ids",
                "=",
                False,
            ),  # Sin restricciones - accesible para todos
            (
                "allowed_group_ids",
                "in",
                user_groups_ids,
            ),  # Usuario pertenece a algún grupo permitido
        ]

        # Combinar el dominio original con nuestro dominio de filtrado por grupos
        if domain:
            domain = expression.AND([domain, group_domain])
        else:
            domain = group_domain

        # Ahora dejar que la implementación estándar maneje la búsqueda con el dominio combinado
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid,
        )

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Override name_search to enforce access restriction."""
        # Call search with bypass_group_check=False to ensure filtering
        domain = args or []
        if name:
            domain = expression.AND([domain, [("name", operator, name)]])

        ids = self.search(domain, limit=limit).ids
        records = self.browse(ids)
        return [(record.id, record.display_name) for record in records]
