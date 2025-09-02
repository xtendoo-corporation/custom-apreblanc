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

    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=fields.Date.context_today
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today
    )
    state = fields.Selection([
        ('all', 'Todos los Estados'),
        ('draft', 'Borrador'),
        ('sent', 'Presupuesto Enviado'),
        ('sale', 'Orden de Venta'),
        ('done', 'Bloqueado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='all')

    include_order_lines = fields.Boolean(
        string='Incluir Líneas de Pedido',
        default=True
    )
    include_invoices = fields.Boolean(
        string='Incluir Facturas',
        default=True
    )
    include_payments = fields.Boolean(
        string='Incluir Pagos',
        default=True
    )

    export_file = fields.Binary(string='Archivo Excel', readonly=True)
    export_filename = fields.Char(string='Nombre del Archivo', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Establecer fecha desde hace 30 días por defecto
        today = fields.Date.context_today(self)
        res['date_to'] = today
        res['date_from'] = today.replace(day=1)  # Primer día del mes
        return res

    def action_export(self):
        """Exportar las ventas a Excel"""
        if not xlsxwriter:
            raise UserError(_('La librería xlsxwriter no está instalada. '
                            'Por favor, instálela usando: pip install xlsxwriter'))

        # Crear el archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Crear formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        currency_format = workbook.add_format({'num_format': '#,##0.00'})

        # Exportar órdenes de venta
        self._export_sale_orders(workbook, header_format, date_format, currency_format)

        if self.include_order_lines:
            self._export_sale_order_lines(workbook, header_format, date_format, currency_format)

        if self.include_invoices:
            self._export_invoices(workbook, header_format, date_format, currency_format)

        if self.include_payments:
            self._export_payments(workbook, header_format, date_format, currency_format)

        workbook.close()
        output.seek(0)

        # Generar nombre del archivo
        filename = f'ventas_export_{self.date_from}_{self.date_to}.xlsx'

        # Guardar el archivo
        self.export_file = base64.b64encode(output.getvalue())
        self.export_filename = filename

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.export.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'default_state': 'done'}
        }

    def _get_sale_orders_domain(self):
        """Construir el dominio para filtrar órdenes de venta"""
        domain = [
            ('date_order', '>=', self.date_from),
            ('date_order', '<=', self.date_to),
        ]

        if self.state != 'all':
            domain.append(('state', '=', self.state))

        return domain

    def _export_sale_orders(self, workbook, header_format, date_format, currency_format):
        """Exportar órdenes de venta"""
        worksheet = workbook.add_worksheet('Órdenes de Venta')

        # Headers
        headers = [
            'ID', 'Número', 'Cliente', 'Fecha Pedido', 'Fecha Confirmación',
            'Estado', 'Total Sin Impuestos', 'Impuestos', 'Total',
            'Moneda', 'Vendedor', 'Equipo de Ventas', 'Empresa'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Datos
        domain = self._get_sale_orders_domain()
        sale_orders = self.env['sale.order'].search(domain)

        for row, order in enumerate(sale_orders, 1):
            worksheet.write(row, 0, order.id)
            worksheet.write(row, 1, order.name)
            worksheet.write(row, 2, order.partner_id.name)
            worksheet.write(row, 3, order.date_order, date_format)
            worksheet.write(row, 4, order.confirmation_date, date_format)
            worksheet.write(row, 5, dict(order._fields['state'].selection)[order.state])
            worksheet.write(row, 6, order.amount_untaxed, currency_format)
            worksheet.write(row, 7, order.amount_tax, currency_format)
            worksheet.write(row, 8, order.amount_total, currency_format)
            worksheet.write(row, 9, order.currency_id.name)
            worksheet.write(row, 10, order.user_id.name)
            worksheet.write(row, 11, order.team_id.name if order.team_id else '')
            worksheet.write(row, 12, order.company_id.name)

    def _export_sale_order_lines(self, workbook, header_format, date_format, currency_format):
        """Exportar líneas de órdenes de venta"""
        worksheet = workbook.add_worksheet('Líneas de Pedido')

        # Headers
        headers = [
            'ID', 'Orden ID', 'Número Orden', 'Producto', 'Descripción',
            'Cantidad', 'Precio Unitario', 'Descuento', 'Subtotal',
            'Unidad de Medida'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Datos
        domain = self._get_sale_orders_domain()
        sale_orders = self.env['sale.order'].search(domain)

        row = 1
        for order in sale_orders:
            for line in order.order_line:
                worksheet.write(row, 0, line.id)
                worksheet.write(row, 1, order.id)
                worksheet.write(row, 2, order.name)
                worksheet.write(row, 3, line.product_id.name if line.product_id else '')
                worksheet.write(row, 4, line.name)
                worksheet.write(row, 5, line.product_uom_qty)
                worksheet.write(row, 6, line.price_unit, currency_format)
                worksheet.write(row, 7, line.discount)
                worksheet.write(row, 8, line.price_subtotal, currency_format)
                worksheet.write(row, 9, line.product_uom.name if line.product_uom else '')
                row += 1

    def _export_invoices(self, workbook, header_format, date_format, currency_format):
        """Exportar facturas relacionadas"""
        worksheet = workbook.add_worksheet('Facturas')

        # Headers
        headers = [
            'ID', 'Número', 'Orden Venta', 'Cliente', 'Fecha Factura',
            'Fecha Vencimiento', 'Estado', 'Total Sin Impuestos', 'Impuestos', 'Total'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Datos
        domain = self._get_sale_orders_domain()
        sale_orders = self.env['sale.order'].search(domain)

        row = 1
        for order in sale_orders:
            for invoice in order.invoice_ids:
                worksheet.write(row, 0, invoice.id)
                worksheet.write(row, 1, invoice.name)
                worksheet.write(row, 2, order.name)
                worksheet.write(row, 3, invoice.partner_id.name)
                worksheet.write(row, 4, invoice.invoice_date, date_format)
                worksheet.write(row, 5, invoice.invoice_date_due, date_format)
                worksheet.write(row, 6, dict(invoice._fields['state'].selection)[invoice.state])
                worksheet.write(row, 7, invoice.amount_untaxed, currency_format)
                worksheet.write(row, 8, invoice.amount_tax, currency_format)
                worksheet.write(row, 9, invoice.amount_total, currency_format)
                row += 1

    def _export_payments(self, workbook, header_format, date_format, currency_format):
        """Exportar pagos relacionados"""
        worksheet = workbook.add_worksheet('Pagos')

        # Headers
        headers = [
            'ID', 'Número', 'Cliente', 'Fecha', 'Importe',
            'Estado', 'Método de Pago', 'Referencia'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Datos - buscar pagos relacionados con las facturas de las órdenes
        domain = self._get_sale_orders_domain()
        sale_orders = self.env['sale.order'].search(domain)

        row = 1
        for order in sale_orders:
            for invoice in order.invoice_ids:
                for payment in invoice.payment_ids:
                    worksheet.write(row, 0, payment.id)
                    worksheet.write(row, 1, payment.name)
                    worksheet.write(row, 2, payment.partner_id.name)
                    worksheet.write(row, 3, payment.date, date_format)
                    worksheet.write(row, 4, payment.amount, currency_format)
                    worksheet.write(row, 5, dict(payment._fields['state'].selection)[payment.state])
                    worksheet.write(row, 6, payment.payment_method_id.name if payment.payment_method_id else '')
                    worksheet.write(row, 7, payment.ref or '')
                    row += 1

    def action_download(self):
        """Descargar el archivo Excel generado"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=sale.export.wizard&id={self.id}&field=export_file&download=true&filename={self.export_filename}',
            'target': 'self',
        }
