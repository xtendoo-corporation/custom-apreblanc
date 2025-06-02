# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain=[('customer_rank', '>', 0)],
        help='Default customer for this quotation template'
    )

    allowed_user_ids = fields.Many2many(
        'res.users',
        'sale_order_template_user_rel',
        'template_id',
        'user_id',
        string='Allowed Users',
        help="Users who can access this template. If empty, all users can access it."
    )

    def check_access_for_current_user(self):
        """Check if current user has access to this template"""
        self.ensure_one()

        # Administrators always have access
        if self.env.user.has_group('base.group_system'):
            return True

        # If no users are specified, everyone has access
        if not self.allowed_user_ids:
            return True

        # Otherwise, check if current user is in allowed_user_ids
        return self.env.user.id in self.allowed_user_ids.ids

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
