# -*- coding: utf-8 -*-
# Copyright 2025 Xtendoo Software
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html)

import base64
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
except ImportError:
    openpyxl = None


class SaleImportWizard(models.TransientModel):
    _name = 'sale.import.wizard'
    _description = 'Wizard para Importar Ventas'

    import_file = fields.Binary(
        string='Archivo Excel',
        required=True,
        help='Seleccione el archivo Excel con las ventas a importar'
    )
    import_filename = fields.Char(string='Nombre del Archivo')

    import_mode = fields.Selection([
        ('create', 'Crear Nuevos Registros'),
        ('update', 'Actualizar Existentes'),
        ('create_update', 'Crear y Actualizar'),
    ], string='Modo de Importación', default='create', required=True)

    validate_data = fields.Boolean(
        string='Validar Datos',
        default=True,
        help='Validar que los datos sean correctos antes de importar'
    )

    log_ids = fields.One2many(
        'sale.import.log',
        'wizard_id',
        string='Log de Importación'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('processing', 'Procesando'),
        ('done', 'Completado'),
        ('error', 'Error')
    ], default='draft')

    summary = fields.Text(string='Resumen', readonly=True)

    def action_import(self):
        """Importar las ventas desde Excel"""
        if not openpyxl:
            raise UserError(_('La librería openpyxl no está instalada. '
                            'Por favor, instálela usando: pip install openpyxl'))

        if not self.import_file:
            raise UserError(_('Por favor, seleccione un archivo Excel para importar.'))

        self.state = 'processing'

        try:
            # Decodificar el archivo
            file_data = base64.b64decode(self.import_file)
            workbook = openpyxl.load_workbook(io.BytesIO(file_data))

            # Limpiar logs anteriores
            self.log_ids.unlink()

            # Contadores para el resumen
            counters = {
                'orders_created': 0,
                'orders_updated': 0,
                'orders_errors': 0,
                'lines_created': 0,
                'lines_errors': 0,
            }

            # Importar órdenes de venta
            if 'Órdenes de Venta' in workbook.sheetnames:
                self._import_sale_orders(workbook['Órdenes de Venta'], counters)

            # Importar líneas de pedido
            if 'Líneas de Pedido' in workbook.sheetnames and self.import_mode in ['create', 'create_update']:
                self._import_sale_order_lines(workbook['Líneas de Pedido'], counters)

            # Generar resumen
            self._generate_summary(counters)
            self.state = 'done'

        except Exception as e:
            self.state = 'error'
            self._add_log('error', f'Error general durante la importación: {str(e)}')
            raise UserError(_('Error durante la importación: %s') % str(e))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _import_sale_orders(self, worksheet, counters):
        """Importar órdenes de venta"""
        # Leer headers
        headers = {}
        for col, cell in enumerate(worksheet[1], 1):
            if cell.value:
                headers[cell.value] = col

        # Validar headers requeridos
        required_headers = ['Número', 'Cliente', 'Fecha Pedido']
        missing_headers = [h for h in required_headers if h not in headers]
        if missing_headers:
            raise UserError(_('Headers faltantes en la hoja Órdenes de Venta: %s') % ', '.join(missing_headers))

        # Procesar filas
        for row_num in range(2, worksheet.max_row + 1):
            try:
                row_data = {}
                for header, col in headers.items():
                    cell_value = worksheet.cell(row=row_num, column=col).value
                    row_data[header] = cell_value

                if not row_data.get('Número'):
                    continue  # Saltar filas vacías

                self._process_sale_order_row(row_data, counters, row_num)

            except Exception as e:
                counters['orders_errors'] += 1
                self._add_log('error', f'Error en fila {row_num}: {str(e)}')

    def _process_sale_order_row(self, row_data, counters, row_num):
        """Procesar una fila de orden de venta"""
        # Buscar cliente
        partner = self._find_partner(row_data.get('Cliente'))
        if not partner:
            raise ValidationError(f'Cliente no encontrado: {row_data.get("Cliente")}')

        # Buscar orden existente
        existing_order = self.env['sale.order'].search([
            ('name', '=', row_data.get('Número'))
        ], limit=1)

        # Preparar valores
        vals = {
            'name': row_data.get('Número'),
            'partner_id': partner.id,
            'date_order': self._parse_date(row_data.get('Fecha Pedido')),
        }

        # Agregar campos opcionales si están presentes
        if row_data.get('Estado'):
            vals['state'] = self._map_state(row_data.get('Estado'))

        if row_data.get('Vendedor'):
            user = self._find_user(row_data.get('Vendedor'))
            if user:
                vals['user_id'] = user.id

        if row_data.get('Equipo de Ventas'):
            team = self._find_sales_team(row_data.get('Equipo de Ventas'))
            if team:
                vals['team_id'] = team.id

        # Crear o actualizar
        if existing_order and self.import_mode in ['update', 'create_update']:
            existing_order.write(vals)
            counters['orders_updated'] += 1
            self._add_log('info', f'Orden actualizada: {vals["name"]} (fila {row_num})')
        elif not existing_order and self.import_mode in ['create', 'create_update']:
            order = self.env['sale.order'].create(vals)
            counters['orders_created'] += 1
            self._add_log('info', f'Orden creada: {order.name} (fila {row_num})')
        elif existing_order and self.import_mode == 'create':
            self._add_log('warning', f'Orden ya existe, omitida: {vals["name"]} (fila {row_num})')
        else:
            self._add_log('warning', f'Orden no encontrada para actualizar: {vals["name"]} (fila {row_num})')

    def _import_sale_order_lines(self, worksheet, counters):
        """Importar líneas de órdenes de venta"""
        # Leer headers
        headers = {}
        for col, cell in enumerate(worksheet[1], 1):
            if cell.value:
                headers[cell.value] = col

        # Validar headers requeridos
        required_headers = ['Número Orden', 'Producto', 'Cantidad']
        missing_headers = [h for h in required_headers if h not in headers]
        if missing_headers:
            self._add_log('warning', f'Headers faltantes en Líneas de Pedido: {", ".join(missing_headers)}')
            return

        # Procesar filas
        for row_num in range(2, worksheet.max_row + 1):
            try:
                row_data = {}
                for header, col in headers.items():
                    cell_value = worksheet.cell(row=row_num, column=col).value
                    row_data[header] = cell_value

                if not row_data.get('Número Orden'):
                    continue

                self._process_sale_order_line_row(row_data, counters, row_num)

            except Exception as e:
                counters['lines_errors'] += 1
                self._add_log('error', f'Error en línea fila {row_num}: {str(e)}')

    def _process_sale_order_line_row(self, row_data, counters, row_num):
        """Procesar una fila de línea de orden"""
        # Buscar orden
        order = self.env['sale.order'].search([
            ('name', '=', row_data.get('Número Orden'))
        ], limit=1)

        if not order:
            raise ValidationError(f'Orden no encontrada: {row_data.get("Número Orden")}')

        # Buscar producto
        product = self._find_product(row_data.get('Producto'))
        if not product:
            raise ValidationError(f'Producto no encontrado: {row_data.get("Producto")}')

        # Preparar valores
        vals = {
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': float(row_data.get('Cantidad', 1)),
            'name': row_data.get('Descripción') or product.name,
        }

        if row_data.get('Precio Unitario'):
            vals['price_unit'] = float(row_data.get('Precio Unitario'))

        if row_data.get('Descuento'):
            vals['discount'] = float(row_data.get('Descuento'))

        # Crear línea
        self.env['sale.order.line'].create(vals)
        counters['lines_created'] += 1
        self._add_log('info', f'Línea creada para orden {order.name} (fila {row_num})')

    def _find_partner(self, partner_name):
        """Buscar partner por nombre"""
        if not partner_name:
            return None
        return self.env['res.partner'].search([
            ('name', 'ilike', partner_name)
        ], limit=1)

    def _find_product(self, product_name):
        """Buscar producto por nombre"""
        if not product_name:
            return None
        return self.env['product.product'].search([
            '|',
            ('name', 'ilike', product_name),
            ('default_code', '=', product_name)
        ], limit=1)

    def _find_user(self, user_name):
        """Buscar usuario por nombre"""
        if not user_name:
            return None
        return self.env['res.users'].search([
            ('name', 'ilike', user_name)
        ], limit=1)

    def _find_sales_team(self, team_name):
        """Buscar equipo de ventas por nombre"""
        if not team_name:
            return None
        return self.env['crm.team'].search([
            ('name', 'ilike', team_name)
        ], limit=1)

    def _parse_date(self, date_value):
        """Parsear fecha desde Excel"""
        if not date_value:
            return fields.Date.today()

        if isinstance(date_value, str):
            try:
                from datetime import datetime
                return datetime.strptime(date_value, '%d/%m/%Y').date()
            except:
                return fields.Date.today()

        return date_value

    def _map_state(self, state_text):
        """Mapear texto de estado a valores de Odoo"""
        state_mapping = {
            'Borrador': 'draft',
            'Presupuesto Enviado': 'sent',
            'Orden de Venta': 'sale',
            'Bloqueado': 'done',
            'Cancelado': 'cancel',
        }
        return state_mapping.get(state_text, 'draft')

    def _add_log(self, level, message):
        """Agregar entrada al log"""
        self.env['sale.import.log'].create({
            'wizard_id': self.id,
            'level': level,
            'message': message,
        })

    def _generate_summary(self, counters):
        """Generar resumen de la importación"""
        summary = f"""
Resumen de Importación:
======================

Órdenes de Venta:
- Creadas: {counters['orders_created']}
- Actualizadas: {counters['orders_updated']}
- Errores: {counters['orders_errors']}

Líneas de Pedido:
- Creadas: {counters['lines_created']}
- Errores: {counters['lines_errors']}

Total de registros procesados: {sum(counters.values())}
        """
        self.summary = summary


class SaleImportLog(models.TransientModel):
    _name = 'sale.import.log'
    _description = 'Log de Importación de Ventas'
    _order = 'id desc'

    wizard_id = fields.Many2one('sale.import.wizard', required=True, ondelete='cascade')
    level = fields.Selection([
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
    ], required=True)
    message = fields.Text(required=True)
