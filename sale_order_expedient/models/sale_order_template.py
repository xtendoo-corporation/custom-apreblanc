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
