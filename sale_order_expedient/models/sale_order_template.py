# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain=[('customer_rank', '>', 0)],
        help='Default customer for this quotation template'
    )

    allowed_group_ids = fields.Many2many(
        'res.groups',
        'sale_template_groups_rel',
        'template_id',
        'group_id',
        string='Allowed Groups',
        help='If groups are selected, only users belonging to these groups will be able to use this template.'
    )

    is_expedient_template = fields.Boolean(
        string='Is Expedient Template',
        help='Indicates if this template is for expedients',
        default=False
    )

    can_use_template = fields.Boolean(
        string='Can Use Template',
        compute='_compute_can_use_template',
        help='Indicates if the current user can use this template'
    )

    is_restricted = fields.Boolean(
        string='Restringida',
        compute='_compute_is_restricted',
        store=True,
        help='Indicates if this template is restricted to certain groups'
    )

    @api.depends('allowed_group_ids')
    def _compute_can_use_template(self):
        """Determine if the current user can use this template based on groups"""
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')

        for template in self:
            # Administrators can always use all templates
            if is_admin:
                template.can_use_template = True
                continue

            # If no groups are assigned, everyone can use it
            if not template.allowed_group_ids:
                template.can_use_template = True
                continue

            # Check if the user belongs to any of the assigned groups
            user_groups = current_user.groups_id
            template.can_use_template = bool(set(template.allowed_group_ids.ids) & set(user_groups.ids))

    @api.depends('allowed_group_ids')
    def _compute_is_restricted(self):
        """Calculates if the template is restricted based on assigned groups"""
        for template in self:
            template.is_restricted = bool(template.allowed_group_ids)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to filter templates by allowed users"""
        if domain is None:
            domain = []

        # Add user access filter
        user_domain = [
            '|',
            ('allowed_user_ids', '=', False),  # No restrictions
            ('allowed_user_ids', 'in', [self.env.user.id])  # Current user is allowed
        ]
        domain = domain + user_domain

        return super().search_read(domain, fields, offset, limit, order)

    @api.model
    def search(self, domain, offset=0, limit=None, order=None, count=False):
        """Override search to filter templates by allowed users"""
        if domain is None:
            domain = []

        # Add user access filter
        user_domain = [
            '|',
            ('allowed_user_ids', '=', False),  # No restrictions
            ('allowed_user_ids', 'in', [self.env.user.id])  # Current user is allowed
        ]
        domain = domain + user_domain

        return super().search(domain, offset, limit, order, count)

    @api.onchange('is_expedient_template')
    def _onchange_is_expedient_template(self):
        """Mostrar mensaje cuando se marca como plantilla de expediente"""
        if self.is_expedient_template:
            return {
                'warning': {
                    'title': 'Plantilla de Expediente',
                    'message': 'Recuerde que debe seleccionar un cliente para esta plantilla de expediente.'
                }
            }

    @api.constrains('is_expedient_template', 'partner_id')
    def _check_expedient_template_partner(self):
        """Verificar que las plantillas de expediente tengan un cliente seleccionado"""
        for template in self:
            if template.is_expedient_template and not template.partner_id:
                raise models.ValidationError('Las plantillas de expediente deben tener un cliente seleccionado.')

    is_expedient_template = fields.Boolean(
        string='Plantilla de Expediente',
        help='Marcar si esta plantilla se utilizará para crear expedientes',
        default=False
    )

    # Redefinir partner_id para hacerlo obligatorio cuando es plantilla de expediente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        help='Cliente asociado a esta plantilla de expediente'
    )

    # Campo para definir grupos permitidos para esta plantilla
    allowed_group_ids = fields.Many2many(
        'res.groups',
        'sale_template_groups_rel',
        'template_id',
        'group_id',
        string='Grupos Permitidos',
        help='Solo los usuarios que pertenezcan a estos grupos podrán usar esta plantilla'
    )

    @api.constrains('is_expedient_template', 'partner_id', 'allowed_group_ids')
    def _check_expedient_template_required_fields(self):
        """Verificar que las plantillas de expediente tengan los campos obligatorios"""
        for template in self:
            if template.is_expedient_template:
                if not template.partner_id:
                    raise ValidationError(_('Las plantillas de expediente deben tener un cliente seleccionado.'))
                if not template.allowed_group_ids:
                    raise ValidationError(_('Las plantillas de expediente deben tener al menos un grupo de usuarios asignado.'))
