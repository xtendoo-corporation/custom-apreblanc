# -*- coding: utf-8 -*-
# Copyright 2025 Xtendoo Software
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html)

import base64
import io
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class SaleExportWizard(models.TransientModel):
    _name = 'sale.export.wizard'
    _description = 'Wizard para Exportar Ventas'

    include_order_lines = fields.Boolean(
        string='Incluir Líneas de Pedido',
        default=True,
        help='Incluir detalles de las líneas de pedido en la exportación'
    )
    include_invoices = fields.Boolean(
        string='Incluir Facturas',
        default=True,
        help='Incluir información de facturas relacionadas'
    )

    export_filename = fields.Char(
        string='Nombre del Archivo',
        default='ventas_export.xlsx'
    )
    export_file = fields.Binary(
        string='Archivo de Exportación'
    )

    def action_export_sales(self):
        """Exportar ventas a Excel"""
        if not xlsxwriter:
            raise UserError(_('La librería xlsxwriter no está instalada. '
                            'Por favor instálela usando: pip install xlsxwriter'))

        # Crear el archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Exportar ventas
        self._export_sales_data(workbook)

        # Exportar líneas de pedido si está habilitado
        if self.include_order_lines:
            self._export_order_lines_data(workbook)

        # Exportar facturas si está habilitado
        if self.include_invoices:
            self._export_invoices_data(workbook)

        workbook.close()
        output.seek(0)

        # Guardar el archivo
        self.export_file = base64.b64encode(output.read())
        self.export_filename = f'ventas_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=sale.export.wizard&id={self.id}&field=export_file&download=true&filename={self.export_filename}',
            'target': 'self',
        }

    def _export_sales_data(self, workbook):
        """Exportar datos de órdenes de venta"""
        worksheet = workbook.add_worksheet('Ordenes de Venta')

        # Estilo para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })

        # Encabezados
        headers = [
            'ID', 'Número', 'Cliente', 'Fecha Pedido', 'Estado',
            'Total Sin Impuestos', 'Impuestos', 'Total', 'Moneda',
            'Vendedor', 'Equipo de Ventas', 'Fecha Confirmación'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Obtener todas las órdenes de venta
        sale_orders = self.env['sale.order'].search([])

        # Escribir datos
        for row, order in enumerate(sale_orders, 1):
            worksheet.write(row, 0, order.id)
            worksheet.write(row, 1, order.name)
            worksheet.write(row, 2, order.partner_id.name)
            worksheet.write(row, 3, order.date_order.strftime('%Y-%m-%d') if order.date_order else '')
            worksheet.write(row, 4, dict(order._fields['state'].selection).get(order.state))
            worksheet.write(row, 5, order.amount_untaxed)
            worksheet.write(row, 6, order.amount_tax)
            worksheet.write(row, 7, order.amount_total)
            worksheet.write(row, 8, order.currency_id.name)
            worksheet.write(row, 9, order.user_id.name if order.user_id else '')
            worksheet.write(row, 10, order.team_id.name if order.team_id else '')
            worksheet.write(row, 11, order.date_order.strftime('%Y-%m-%d') if order.date_order else '')

    def _export_order_lines_data(self, workbook):
        """Exportar líneas de pedido"""
        worksheet = workbook.add_worksheet('Lineas de Pedido')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })

        headers = [
            'ID Línea', 'ID Pedido', 'Número Pedido', 'Producto',
            'Descripción', 'Cantidad', 'Precio Unitario', 'Descuento',
            'Subtotal', 'Impuestos'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Obtener todas las líneas de pedido
        sale_orders = self.env['sale.order'].search([])
        order_lines = sale_orders.mapped('order_line')

        for row, line in enumerate(order_lines, 1):
            worksheet.write(row, 0, line.id)
            worksheet.write(row, 1, line.order_id.id)
            worksheet.write(row, 2, line.order_id.name)
            worksheet.write(row, 3, line.product_id.name if line.product_id else '')
            worksheet.write(row, 4, line.name)
            worksheet.write(row, 5, line.product_uom_qty)
            worksheet.write(row, 6, line.price_unit)
            worksheet.write(row, 7, line.discount)
            worksheet.write(row, 8, line.price_subtotal)
            worksheet.write(row, 9, ', '.join(line.tax_id.mapped('name')))

    def _export_invoices_data(self, workbook):
        """Exportar facturas relacionadas"""
        worksheet = workbook.add_worksheet('Facturas')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })

        headers = [
            'ID Factura', 'Número', 'ID Pedido', 'Número Pedido',
            'Cliente', 'Fecha', 'Fecha Vencimiento', 'Estado',
            'Total Sin Impuestos', 'Impuestos', 'Total'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Obtener facturas relacionadas con todos los pedidos
        sale_orders = self.env['sale.order'].search([])
        invoices = sale_orders.mapped('invoice_ids')

        for row, invoice in enumerate(invoices, 1):
            worksheet.write(row, 0, invoice.id)
            worksheet.write(row, 1, invoice.name)
            worksheet.write(row, 2, invoice.invoice_origin)
            worksheet.write(row, 3, invoice.invoice_origin)
            worksheet.write(row, 4, invoice.partner_id.name)
            worksheet.write(row, 5, invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '')
            worksheet.write(row, 6, invoice.invoice_date_due.strftime('%Y-%m-%d') if invoice.invoice_date_due else '')
            worksheet.write(row, 7, dict(invoice._fields['state'].selection).get(invoice.state))
            worksheet.write(row, 8, invoice.amount_untaxed)
            worksheet.write(row, 9, invoice.amount_tax)
            worksheet.write(row, 10, invoice.amount_total)
