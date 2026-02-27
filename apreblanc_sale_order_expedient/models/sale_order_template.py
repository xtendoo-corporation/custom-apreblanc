# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

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
