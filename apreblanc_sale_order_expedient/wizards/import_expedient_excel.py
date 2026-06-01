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

    # Campo para seleccionar el cliente al que se asignarán todos los expedientes
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        help='Cliente al que se asignarán todos los expedientes importados'
    )

    # Opciones de importación
    expedient_type = fields.Selection([
        ('post_paid', 'Post-pagado'),
        ('pre_paid', 'Pre-pagado'),
    ],
        string='Tipo de Expediente',
        required=True,
        default='post_paid',
        help='Seleccione el tipo de expediente que desea importar'
    )

    # Barra de progreso
    progress = fields.Float(string="Progreso", default=0.0, readonly=True)
    progress_text = fields.Char(string="Estado de la importación", readonly=True)

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
    ],
        default='draft',
        string='Estado'
    )

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

        # Cambiar a modo de procesamiento
        self.write({
            'state': 'draft',
            'progress': 0.0,
            'progress_text': 'Iniciando importación...'
        })
        # Forzar actualización de la UI
        self.env.cr.commit()

        try:
            # Decodificar archivo Excel
            excel_data = base64.b64decode(self.excel_file)
            book = xlrd.open_workbook(file_contents=excel_data)
            sheet = book.sheet_by_index(0)

            # Validar que el archivo tiene el formato esperado
            if sheet.nrows < 2:  # Al menos una fila de encabezado y una de datos
                raise UserError(_('El archivo Excel no tiene datos.'))

            # Calcular el total de filas para la barra de progreso
            total_rows = sheet.nrows - 1  # Restamos 1 para excluir la fila de encabezado

            # Actualizar progreso: inicio
            self.write({
                'progress': 5.0,  # 5% inicial
                'progress_text': f'Analizando {total_rows} registros...'
            })
            self.env.cr.commit()  # Forzar actualización de la UI
            sale_order_type = self.env['sale.order']._get_expedient_sale_order_type(
                self.expedient_type
            )
            type_id_vals = sale_order_type.id if sale_order_type else False

            # Leer datos desde la segunda fila (índice 1), asumiendo que la primera fila es encabezado
            for row_index in range(1, sheet.nrows):
                total += 1
                try:
                    # Actualizar barra de progreso periódicamente (cada 10 filas o según necesidad)
                    if row_index % 10 == 0 or row_index == 1:
                        progress_percent = 5.0 + ((row_index / total_rows) * 90.0)  # 5% al inicio, hasta 95% al final
                        self.write({
                            'progress': progress_percent,
                            'progress_text': f'Procesando registro {row_index}/{total_rows} ({int(progress_percent)}%)'
                        })
                        self.env.cr.commit()  # Forzar actualización de la UI

                    # Columna B (índice 1): Ahora es "person_under_study" en lugar del nombre del cliente
                    person_under_study = sheet.cell_value(row_index, 1)

                    # Columna D (índice 3): Procesar el tipo de persona (PF/PJ)
                    person_type_value = sheet.cell_value(row_index, 3)
                    person_type = False
                    if isinstance(person_type_value, str):
                        person_type_value = person_type_value.upper().strip()
                        if person_type_value == 'PF':
                            person_type = 'fisica'
                        elif person_type_value == 'PJ':
                            person_type = 'juridica'

                    # Obtener la dificultad del expediente de la columna E (índice 4)
                    expedient_difficulty = sheet.cell_value(row_index, 4)

                    # Extraer las claves compuestas: client_id y expedient_number (columnas F y G)
                    client_id = sheet.cell_value(row_index, 5)  # Columna F (índice 5)
                    expedient_number = sheet.cell_value(row_index, 6)  # Columna G (índice 6)

                    if not client_id or not expedient_number:
                        log_messages.append(f"Fila {row_index + 1}: Omitida - Falta Client ID o Expedient Number")
                        skipped += 1
                        continue

                    # Convertir a string si son números
                    if isinstance(client_id, (int, float)):
                        client_id = str(int(client_id))
                    if isinstance(expedient_number, (int, float)):
                        expedient_number = str(int(expedient_number))
                    if isinstance(person_under_study, (int, float)):
                        person_under_study = str(int(person_under_study))

                    # Resolver person_under_study como Many2one a res.partner
                    person_under_study_id = False
                    if person_under_study:
                        study_partner = self.env['res.partner'].search([
                            ('name', '=', person_under_study),
                            ('is_study_entity', '=', True),
                        ], limit=1)
                        if not study_partner:
                            study_partner = self.env['res.partner'].create({
                                'name': person_under_study,
                                'is_study_entity': True,
                            })
                            log_messages.append(
                                f"Fila {row_index + 1}: Contacto creado automáticamente '{person_under_study}'"
                            )
                        person_under_study_id = study_partner.id

                    # Verificar si ya existe un registro con esta clave compuesta
                    existing_order = self.env['sale.order'].search([
                        ('client_id', '=', client_id),
                        ('expedient_number', '=', expedient_number)
                    ], limit=1)

                    # Preparar los valores para crear/actualizar
                    vals = {
                        'partner_id': self.partner_id.id,  # Usar el partner seleccionado en el wizard
                        'client_id': client_id,
                        'expedient_number': expedient_number,
                        'expedient_type': self.expedient_type,  # Usar el tipo seleccionado por el usuario
                        'expedient_state': 'creada',
                        'person_under_study_id': person_under_study_id,  # Many2one a res.partner
                        'person_type': person_type,  # Tipo de persona (física/jurídica)
                    }

                    if type_id_vals:
                        vals['type_id'] = type_id_vals  # Tipo de venta basado en el tipo de expediente

                    # Procesar la dificultad del expediente (columna E)
                    if expedient_difficulty:
                        if isinstance(expedient_difficulty, str):
                            expedient_difficulty = expedient_difficulty.lower()
                            if 'simple' in expedient_difficulty:
                                vals['expedient_difficulty'] = 'simple'
                            elif 'compl' in expedient_difficulty:
                                vals['expedient_difficulty'] = 'complex'
                        elif isinstance(expedient_difficulty, (int, float)):
                            # Si es un número, interpretamos 1 como simple y 2 como complejo
                            if int(expedient_difficulty) == 1:
                                vals['expedient_difficulty'] = 'simple'
                            elif int(expedient_difficulty) == 2:
                                vals['expedient_difficulty'] = 'complex'

                        if 'expedient_difficulty' in vals:
                            log_messages.append(f"Fila {row_index + 1}: Dificultad establecida a '{vals['expedient_difficulty']}'")

                    # Obtener valor de columna I: date_reception (índice 8)
                    if sheet.ncols > 8:
                        date_reception_value = sheet.cell_value(row_index, 8)
                        if isinstance(date_reception_value, (int, float)) and date_reception_value:
                            # Convertir el número de Excel a fecha
                            try:
                                date_reception = xlrd.xldate.xldate_as_datetime(date_reception_value, book.datemode)
                                vals['date_reception'] = fields.Datetime.to_string(date_reception)
                                log_messages.append(
                                    f"Fila {row_index + 1}: Fecha de recepción establecida a '{date_reception}'")
                            except Exception as e:
                                _logger.warning(f"Error al convertir fecha date_reception: {e}")
                        elif isinstance(date_reception_value, str) and date_reception_value.strip():
                            # Intentar procesar como string de fecha (formato ISO)
                            try:
                                vals['date_reception'] = date_reception_value
                                log_messages.append(f"Fila {row_index + 1}: Fecha de recepción (texto) establecida")
                            except Exception as e:
                                _logger.warning(f"Error al procesar fecha date_reception como string: {e}")
                    # Obtener valor de columna I: date_order (índice 8)
                    if sheet.ncols > 9:
                        date_order_value = sheet.cell_value(row_index, 9)
                        if isinstance(date_order_value, (int, float)) and date_order_value:
                            # Convertir el número de Excel a fecha
                            try:
                                date_order = xlrd.xldate.xldate_as_datetime(date_order_value, book.datemode)
                                vals['date_order'] = fields.Datetime.to_string(date_order)
                                log_messages.append(
                                    f"Fila {row_index + 1}: Fecha de pedido establecida a '{date_order}'")
                            except Exception as e:
                                _logger.warning(f"Error al convertir fecha date_order: {e}")
                        elif isinstance(date_order_value, str) and date_order_value.strip():
                            # Intentar procesar como string de fecha (formato ISO)
                            try:
                                vals['date_order'] = date_order_value
                            except Exception as e:
                                _logger.warning(f"Error al procesar fecha date_order como string: {e}")

                    # Obtener valor de columna K: expedient_state (índice 10)
                    if sheet.ncols > 10:
                        state_value = sheet.cell_value(row_index, 10)
                        if isinstance(state_value, str) and state_value.strip():
                            state_value = state_value.lower().strip()
                            # Mapear el valor de texto al valor esperado en Odoo
                            state_mapping = {
                                'creada': 'creada',
                                'pendiente': 'pendiente_documentacion',
                                'pendiente documentacion': 'pendiente_documentacion',
                                'pendiente_documentacion': 'pendiente_documentacion',
                                'pte doc adicional': 'pendiente_documentacion',
                                'pte. doc. adicional': 'pendiente_documentacion',
                                'Pte doc adicional': 'pendiente_documentacion',
                                'Pte. Doc. Adicional': 'pendiente_documentacion',
                                'aprobada': 'aprobada',
                                'autorizada': 'aprobada',
                                'Autorizada': 'aprobada',
                                'rechazada': 'rechazada',
                                'cancelada': 'cancelada',
                                'CANCELADA': 'cancelada',
                                'cn': 'cancelada'
                            }

                            if state_value in state_mapping:
                                vals['expedient_state'] = state_mapping[state_value]
                                log_messages.append(f"Fila {row_index + 1}: Estado establecido a '{vals['expedient_state']}'")
                            else:
                                # Si no se reconoce, intentar hacer coincidencia parcial para casos no contemplados
                                for key, value in state_mapping.items():
                                    if key in state_value:
                                        vals['expedient_state'] = value
                                        log_messages.append(f"Fila {row_index + 1}: Estado '{state_value}' mapeado a '{value}' por coincidencia parcial")
                                        break

                    # Obtener valor de columna M: expedient_date_end (índice 12)
                    if sheet.ncols > 12:
                        end_date_value = sheet.cell_value(row_index, 12)
                        if isinstance(end_date_value, (int, float)) and end_date_value:
                            # Convertir el número de Excel a fecha
                            try:
                                end_date = xlrd.xldate.xldate_as_datetime(end_date_value, book.datemode)
                                vals['expedient_date_end'] = fields.Datetime.to_string(end_date)
                                log_messages.append(f"Fila {row_index + 1}: Fecha de fin establecida a '{end_date}'")
                            except Exception as e:
                                _logger.warning(f"Error al convertir fecha expedient_date_end: {e}")
                        elif isinstance(end_date_value, str) and end_date_value.strip():
                            # Intentar procesar como string de fecha (formato ISO)
                            try:
                                vals['expedient_date_end'] = end_date_value
                            except Exception as e:
                                _logger.warning(f"Error al procesar fecha expedient_date_end como string: {e}")

                    # Obtener valor de columna N: request (índice 13)
                    if sheet.ncols > 13:
                        request_value = sheet.cell_value(row_index, 13)
                        if isinstance(request_value, str) and request_value.strip():
                            vals['request'] = request_value
                            log_messages.append(f"Fila {row_index + 1}: Petición del expediente capturada")
                        elif isinstance(request_value, (int, float)):
                            # Convertir a string si es un número
                            vals['request'] = str(request_value)
                            log_messages.append(f"Fila {row_index + 1}: Petición del expediente (convertida de número) capturada")

                    # Obtener valor de columna O: summary (índice 14)
                    if sheet.ncols > 14:
                        summary_value = sheet.cell_value(row_index, 14)
                        if isinstance(summary_value, str) and summary_value.strip():
                            vals['summary'] = summary_value
                            log_messages.append(f"Fila {row_index + 1}: Resumen del expediente capturado")
                        elif isinstance(summary_value, (int, float)):
                            # Convertir a string si es un número
                            vals['summary'] = str(summary_value)
                            log_messages.append(f"Fila {row_index + 1}: Resumen del expediente (convertido de número) capturado")

                    # Obtener valor de columna P: authorization (índice 15)
                    if sheet.ncols > 15:
                        authorization_value = sheet.cell_value(row_index, 15)
                        if isinstance(authorization_value, str) and authorization_value.strip():
                            vals['authorization'] = authorization_value
                            log_messages.append(f"Fila {row_index + 1}: Autorización del expediente capturada")
                        elif isinstance(authorization_value, (int, float)):
                            # Convertir a string si es un número
                            vals['authorization'] = str(authorization_value)
                            log_messages.append(f"Fila {row_index + 1}: Autorización del expediente (convertida de número) capturada")

                    # Otras columnas que se pueden mapear
                    try:
                        # Ejemplo de mapeo de campos adicionales
                        # if sheet.ncols > 7:  # Si hay columna H
                        #     parts_involved = sheet.cell_value(row_index, 7)
                        #     if isinstance(parts_involved, (int, float)) and parts_involved > 0:
                        #         vals['parts_involved'] = int(parts_involved)

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
                        # Siempre actualizamos registros existentes
                        existing_order.write(vals)
                        updated += 1
                        log_messages.append(f"Fila {row_index + 1}: Actualizado - {client_id}/{expedient_number}")
                    else:
                        # Obtener la secuencia correcta según el tipo de expediente
                        sequence_code = 'sale.order.post' if self.expedient_type == 'post_paid' else 'sale.order.pre'
                        sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)

                        if sequence:
                            # Generar el número de la secuencia
                            sequence_number = sequence.next_by_id()
                            vals['name'] = sequence_number
                            log_messages.append(f"Fila {row_index + 1}: Número de secuencia generado: {sequence_number}")

                        # Creamos un pedido de venta
                        vals.update({
                            'state': 'draft',
                        })
                        self.env['sale.order'].create(vals)
                        created += 1
                        log_messages.append(f"Fila {row_index + 1}: Creado - {client_id}/{expedient_number}")

                except Exception as row_error:
                    failed += 1
                    log_messages.append(f"Fila {row_index + 1}: Error - {str(row_error)}")
                    _logger.error(f"Error en fila {row_index + 1}: {str(row_error)}")

            # Actualizar progreso: finalización
            self.write({
                'progress': 100.0,
                'progress_text': f'Importación completada: {created} creados, {updated} actualizados'
            })
            self.env.cr.commit()  # Forzar actualización de la UI

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
            # En caso de error, actualizar el progreso
            self.write({
                'progress': 0,
                'progress_text': f'Error: {str(e)}',
                'state': 'draft'
            })
            self.env.cr.commit()
            raise UserError(_(f'Error al procesar el archivo Excel: {str(e)}'))
