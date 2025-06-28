# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import base64
import io
import logging
import xlrd

_logger = logging.getLogger(__name__)


class ImportExpedientExcel(models.TransientModel):
    _name = 'import.expedient.excel'
    _description = 'Asistente para importar expedientes desde Excel'

    excel_file = fields.Binary(string='Archivo Excel', required=True)
    file_name = fields.Char(string='Nombre del archivo')

    # Opciones de importación
    update_existing = fields.Boolean(
        string='Actualizar existentes',
        default=True,
        help='Si está marcado, actualiza los registros existentes. Si no está marcado, omite los registros existentes.'
    )

    # Resultados
    import_total = fields.Integer(string='Total de registros', readonly=True)
    import_created = fields.Integer(string='Registros creados', readonly=True)
    import_updated = fields.Integer(string='Registros actualizados', readonly=True)
    import_skipped = fields.Integer(string='Registros omitidos', readonly=True)
    import_failed = fields.Integer(string='Registros fallidos', readonly=True)

    # Log de importación
    import_log = fields.Text(string='Log de importación', readonly=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Importado')
    ], default='draft', string='Estado')

    def action_import_excel(self):
        """Importar datos de expedientes desde archivo Excel"""
        self.ensure_one()
        if not self.excel_file:
            raise UserError(_('Por favor, seleccione un archivo Excel.'))

        # Inicializar contadores
        created = 0
        updated = 0
        skipped = 0
        failed = 0
        total = 0
        log_messages = []

        try:
            # Decodificar archivo Excel
            excel_data = base64.b64decode(self.excel_file)
            book = xlrd.open_workbook(file_contents=excel_data)
            sheet = book.sheet_by_index(0)

            # Validar que el archivo tiene el formato esperado
            if sheet.nrows < 2:  # Al menos una fila de encabezado y una de datos
                raise UserError(_('El archivo Excel no tiene datos.'))

            # Leer datos desde la segunda fila (índice 1), asumiendo que la primera fila es encabezado
            for row_index in range(1, sheet.nrows):
                total += 1
                try:
                    # Extraer las claves compuestas: client_id y expedient_number (columnas F y G)
                    client_id = sheet.cell_value(row_index, 5)  # Columna F (índice 5)
                    expedient_number = sheet.cell_value(row_index, 6)  # Columna G (índice 6)

                    if not client_id or not expedient_number:
                        log_messages.append(f"Fila {row_index+1}: Omitida - Falta Client ID o Expedient Number")
                        skipped += 1
                        continue

                    # Convertir a string si son números
                    if isinstance(client_id, (int, float)):
                        client_id = str(int(client_id))
                    if isinstance(expedient_number, (int, float)):
                        expedient_number = str(int(expedient_number))

                    # Verificar si ya existe un registro con esta clave compuesta
                    existing_order = self.env['sale.order'].search([
                        ('client_id', '=', client_id),
                        ('expedient_number', '=', expedient_number)
                    ], limit=1)

                    # Preparar los valores para crear/actualizar
                    vals = {
                        'client_id': client_id,
                        'expedient_number': expedient_number,
                        'expedient_type': 'post_paid',  # Por defecto establecemos post_paid
                        'expedient_state': 'creada',
                    }

                    # Otras columnas que se pueden mapear
                    try:
                        # Ejemplo de mapeo de campos adicionales
                        if sheet.ncols > 7:  # Si hay columna H
                            parts_involved = sheet.cell_value(row_index, 7)
                            if isinstance(parts_involved, (int, float)) and parts_involved > 0:
                                vals['parts_involved'] = int(parts_involved)

                        if sheet.ncols > 8:  # Si hay columna I - Dificultad
                            difficulty = sheet.cell_value(row_index, 8)
                            if isinstance(difficulty, str):
                                difficulty = difficulty.lower()
                                if 'simple' in difficulty:
                                    vals['expedient_difficulty'] = 'simple'
                                elif 'compl' in difficulty:
                                    vals['expedient_difficulty'] = 'complex'
                    except Exception as mapping_error:
                        _logger.error(f"Error en mapeo de campos adicionales: {mapping_error}")

                    # Crear o actualizar el registro
                    if existing_order:
                        if self.update_existing:
                            existing_order.write(vals)
                            updated += 1
                            log_messages.append(f"Fila {row_index+1}: Actualizado - {client_id}/{expedient_number}")
                        else:
                            skipped += 1
                            log_messages.append(f"Fila {row_index+1}: Omitido (ya existe) - {client_id}/{expedient_number}")
                    else:
                        # Creamos un pedido de venta
                        # Necesitamos al menos un partner_id
                        partner_id = self.env['res.partner'].search([], limit=1).id
                        vals.update({
                            'partner_id': partner_id,
                            'state': 'draft',
                        })
                        self.env['sale.order'].create(vals)
                        created += 1
                        log_messages.append(f"Fila {row_index+1}: Creado - {client_id}/{expedient_number}")

                except Exception as row_error:
                    failed += 1
                    log_messages.append(f"Fila {row_index+1}: Error - {str(row_error)}")
                    _logger.error(f"Error en fila {row_index+1}: {str(row_error)}")

            # Actualizar resultados
            self.write({
                'import_total': total,
                'import_created': created,
                'import_updated': updated,
                'import_skipped': skipped,
                'import_failed': failed,
                'import_log': '\n'.join(log_messages),
                'state': 'done'
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            raise UserError(_(f'Error al procesar el archivo Excel: {str(e)}'))
