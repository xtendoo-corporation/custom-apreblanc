# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='restrict')
    allowed_user_ids = fields.Many2many(
        'res.users',
        string='Allowed Users',
        help="Only these users will be able to view and use this template. "
             "If empty, all users will have access."
    )

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, access_rights_uid=None):
        # Primero comprobar si el usuario es un administrador
        is_admin = self.env.user.has_group('base.group_system')

        # Si no es un administrador y no tiene acceso forzado
        if not is_admin and not self.env.context.get('show_all_templates'):
            # Modificar el dominio para incluir plantillas donde:
            # 1. El usuario está en allowed_user_ids
            # 2. allowed_user_ids está vacío (lo que significa acceso para todos)
            if not args:
                args = []

            # Usamos un dominio OR para permitir ambas condiciones
            args = ['&', '|', ('allowed_user_ids', '=', False),
                         ('allowed_user_ids', 'in', [self.env.user.id])] + args

        return super()._search(args, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)
