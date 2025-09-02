# -*- coding: utf-8 -*-
# Copyright 2025 Xtendoo Software
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html)

import base64
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

try:
    import pandas as pd
except ImportError:
    pd = None


class SaleImportWizard(models.TransientModel):
    _name = 'sale.import.wizard'
    _description = 'Wizard para Importar Ventas'

    import_file = fields.Binary(
        string='Archivo Excel',
        required=True,
        help='Archivo Excel con los datos de ventas a importar'
    )
    import_filename = fields.Char(
        string='Nombre del Archivo'
    )

    update_existing = fields.Boolean(
        string='Actualizar Existentes',
        default=False,
        help='Si está marcado, actualizará registros existentes en lugar de crear duplicados'
    )

    create_partners = fields.Boolean(
        string='Crear Clientes',
        default=True,
        help='Crear automáticamente clientes que no existan'
    )

    create_products = fields.Boolean(
        string='Crear Productos',
        default=True,
        help='Crear automáticamente productos que no existan'
    )

    import_result = fields.Text(
        string='Resultado de la Importación',
        readonly=True
    )

    def action_import_sales(self):
        """Importar ventas desde Excel"""
        if not pd:
            raise UserError(_('La librería pandas no está instalada. '
                            'Por favor instálela usando: pip install pandas openpyxl'))

        if not self.import_file:
            raise UserError(_('Por favor seleccione un archivo para importar.'))

        # Decodificar el archivo
        file_data = base64.b64decode(self.import_file)
        file_like = io.BytesIO(file_data)

        try:
            # Leer el archivo Excel
            excel_file = pd.ExcelFile(file_like)

            result_messages = []

            # Importar órdenes de venta
            if 'Ordenes de Venta' in excel_file.sheet_names:
                orders_result = self._import_sale_orders(excel_file)
                result_messages.append(orders_result)

            # Importar líneas de pedido
            if 'Lineas de Pedido' in excel_file.sheet_names:
                lines_result = self._import_order_lines(excel_file)
                result_messages.append(lines_result)

            self.import_result = '\n'.join(result_messages)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_import_result': self.import_result}
            }

        except Exception as e:
            raise UserError(_('Error al procesar el archivo: %s') % str(e))

    def _import_sale_orders(self, excel_file):
        """Importar órdenes de venta"""
        df = pd.read_excel(excel_file, sheet_name='Ordenes de Venta')

        created_count = 0
        updated_count = 0
        error_count = 0

        for index, row in df.iterrows():
            try:
                # Buscar o crear cliente
                partner = self._get_or_create_partner(row.get('Cliente', ''))
                if not partner:
                    error_count += 1
                    continue

                # Buscar orden existente
                existing_order = None
                if row.get('Número'):
                    existing_order = self.env['sale.order'].search([
                        ('name', '=', row['Número'])
                    ], limit=1)

                # Preparar valores
                vals = {
                    'partner_id': partner.id,
                    'date_order': pd.to_datetime(row.get('Fecha Pedido')).date() if pd.notna(row.get('Fecha Pedido')) else fields.Date.today(),
                }

                if row.get('Número'):
                    vals['name'] = row['Número']

                if existing_order and self.update_existing:
                    existing_order.write(vals)
                    updated_count += 1
                else:
                    self.env['sale.order'].create(vals)
                    created_count += 1

            except Exception as e:
                error_count += 1
                continue

        return f"Órdenes de Venta: {created_count} creadas, {updated_count} actualizadas, {error_count} errores"

    def _import_order_lines(self, excel_file):
        """Importar líneas de pedido"""
        df = pd.read_excel(excel_file, sheet_name='Lineas de Pedido')

        created_count = 0
        error_count = 0

        for index, row in df.iterrows():
            try:
                # Buscar orden de venta
                order = None
                if row.get('Número Pedido'):
                    order = self.env['sale.order'].search([
                        ('name', '=', row['Número Pedido'])
                    ], limit=1)

                if not order:
                    error_count += 1
                    continue

                # Buscar o crear producto
                product = self._get_or_create_product(row.get('Producto', ''))
                if not product:
                    error_count += 1
                    continue

                # Preparar valores
                vals = {
                    'order_id': order.id,
                    'product_id': product.id,
                    'name': row.get('Descripción', product.name),
                    'product_uom_qty': row.get('Cantidad', 1),
                    'price_unit': row.get('Precio Unitario', 0),
                    'discount': row.get('Descuento', 0),
                }

                self.env['sale.order.line'].create(vals)
                created_count += 1

            except Exception as e:
                error_count += 1
                continue

        return f"Líneas de Pedido: {created_count} creadas, {error_count} errores"

    def _get_or_create_partner(self, partner_name):
        """Obtener o crear cliente"""
        if not partner_name:
            return None

        partner = self.env['res.partner'].search([
            ('name', '=', partner_name)
        ], limit=1)

        if not partner and self.create_partners:
            partner = self.env['res.partner'].create({
                'name': partner_name,
                'is_company': True,
                'customer_rank': 1,
            })

        return partner

    def _get_or_create_product(self, product_name):
        """Obtener o crear producto"""
        if not product_name:
            return None

        product = self.env['product.product'].search([
            ('name', '=', product_name)
        ], limit=1)

        if not product and self.create_products:
            product = self.env['product.product'].create({
                'name': product_name,
                'type': 'product',
                'sale_ok': True,
                'purchase_ok': True,
            })

        return product
