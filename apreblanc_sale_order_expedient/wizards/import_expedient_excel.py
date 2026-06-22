# -*- coding: utf-8 -*-
import base64
import io
import logging
import posixpath
import struct
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta

import xlrd

from odoo import fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)
_UINT8 = struct.Struct("<B")
_INT32 = struct.Struct("<i")
_UINT32 = struct.Struct("<I")
_DOUBLE = struct.Struct("<d")

_XLSB_RECORD_ROW = 0x0000
_XLSB_RECORD_BLANK = 0x0001
_XLSB_RECORD_NUM = 0x0002
_XLSB_RECORD_BOOLERR = 0x0003
_XLSB_RECORD_BOOL = 0x0004
_XLSB_RECORD_FLOAT = 0x0005
_XLSB_RECORD_STRING = 0x0007
_XLSB_RECORD_FORMULA_STRING = 0x0008
_XLSB_RECORD_FORMULA_FLOAT = 0x0009
_XLSB_RECORD_FORMULA_BOOL = 0x000A
_XLSB_RECORD_FORMULA_BOOLERR = 0x000B
_XLSB_RECORD_SHEET = 0x019C
_XLSB_RECORD_SHEETDATA = 0x0191
_XLSB_RECORD_SHEETDATA_END = 0x0192
_XLSB_RECORD_DIMENSION = 0x0194
_XLSB_RECORD_SHARED_STRING = 0x0013
_XLSB_RECORD_SHARED_STRINGS_END = 0x01A0

_XLSB_CELL_RECORDS = {
    _XLSB_RECORD_BLANK,
    _XLSB_RECORD_NUM,
    _XLSB_RECORD_BOOLERR,
    _XLSB_RECORD_BOOL,
    _XLSB_RECORD_FLOAT,
    _XLSB_RECORD_STRING,
    _XLSB_RECORD_FORMULA_STRING,
    _XLSB_RECORD_FORMULA_FLOAT,
    _XLSB_RECORD_FORMULA_BOOL,
    _XLSB_RECORD_FORMULA_BOOLERR,
}


class XlsbPayloadReader:
    def __init__(self, payload):
        self._buffer = io.BytesIO(payload)

    def skip(self, length):
        self._buffer.seek(length, io.SEEK_CUR)

    def read_byte(self):
        data = self._buffer.read(1)
        if not data:
            return None
        return _UINT8.unpack(data)[0]

    def read_uint32(self):
        data = self._buffer.read(4)
        if len(data) < 4:
            return None
        return _UINT32.unpack(data)[0]

    def read_double(self):
        data = self._buffer.read(8)
        if len(data) < 8:
            return None
        return _DOUBLE.unpack(data)[0]

    def read_rk_number(self):
        data = self._buffer.read(4)
        if len(data) < 4:
            return None
        raw_value = _INT32.unpack(data)[0]
        if raw_value & 0x02:
            value = float(raw_value >> 2)
        else:
            value = _DOUBLE.unpack(
                b"\x00\x00\x00\x00" + _UINT32.pack(raw_value & 0xFFFFFFFC)
            )[0]
        if raw_value & 0x01:
            value /= 100
        return value

    def read_wide_string(self):
        length = self.read_uint32()
        if length is None:
            return None
        raw_value = self._buffer.read(length * 2)
        if len(raw_value) < length * 2:
            return None
        return raw_value.decode("utf-16le", errors="replace")


class XlsbRecordStream:
    def __init__(self, raw_data):
        self._buffer = io.BytesIO(raw_data)

    def __iter__(self):
        return self

    def __next__(self):
        record_id = self._read_record_id()
        if record_id is None:
            raise StopIteration
        record_length = self._read_record_length()
        if record_length is None:
            raise StopIteration
        payload = self._buffer.read(record_length)
        return record_id, payload

    def _read_record_id(self):
        value = 0
        for shift in range(0, 32, 8):
            byte = self._buffer.read(1)
            if not byte:
                return None
            byte = _UINT8.unpack(byte)[0]
            value |= byte << shift
            if byte & 0x80 == 0:
                return value
        return value

    def _read_record_length(self):
        value = 0
        for shift in range(0, 28, 7):
            byte = self._buffer.read(1)
            if not byte:
                return None
            byte = _UINT8.unpack(byte)[0]
            value |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return value
        return value


class ImportedExcelSheet:
    def __init__(self, rows, date_converter, source_format):
        self._rows = rows
        self._date_converter = date_converter
        self.source_format = source_format
        self.nrows = len(rows)
        self.ncols = max((len(row) for row in rows), default=0)

    def cell_value(self, row_index, column_index):
        row = self._rows[row_index]
        return row[column_index] if column_index < len(row) else False

    def convert_date(self, value):
        return self._date_converter(value)


class ImportExpedientExcel(models.TransientModel):
    _name = "import.expedient.excel"
    _description = "Asistente para importar expedientes desde Excel"

    _STATE_MAPPING = {
        "creada": "creada",
        "pendiente": "pendiente_documentacion",
        "pendiente documentacion": "pendiente_documentacion",
        "pendiente_documentacion": "pendiente_documentacion",
        "pte doc adicional": "pendiente_documentacion",
        "pte. doc. adicional": "pendiente_documentacion",
        "aprobada": "aprobada",
        "autorizada": "aprobada",
        "rechazada": "rechazada",
        "cancelada": "cancelada",
        "cn": "cancelada",
    }

    excel_file = fields.Binary(string="Archivo Excel", required=True)
    file_name = fields.Char(string="Nombre del archivo")
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        help="Cliente al que se asignarán todos los expedientes importados",
    )
    expedient_type = fields.Selection(
        [
            ("post_paid", "Post-pagado"),
            ("pre_paid", "Pre-pagado"),
        ],
        string="Tipo de Expediente",
        required=True,
        default="post_paid",
        help="Seleccione el tipo de expediente que desea importar",
    )
    progress = fields.Float(string="Progreso", default=0.0, readonly=True)
    progress_text = fields.Char(string="Estado de la importación", readonly=True)
    import_total = fields.Integer(string="Total de registros", readonly=True)
    import_created = fields.Integer(string="Registros creados", readonly=True)
    import_updated = fields.Integer(string="Registros actualizados", readonly=True)
    import_skipped = fields.Integer(string="Registros omitidos", readonly=True)
    import_failed = fields.Integer(string="Registros fallidos", readonly=True)
    import_log = fields.Text(string="Log de importación", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("done", "Importado"),
        ],
        default="draft",
        string="Estado",
    )

    def _load_excel_sheet(self, excel_data):
        if zipfile.is_zipfile(io.BytesIO(excel_data)):
            return self._load_xlsb_sheet(excel_data)
        return self._load_xls_sheet(excel_data)

    def _load_xls_sheet(self, excel_data):
        workbook = xlrd.open_workbook(file_contents=excel_data)
        sheet = workbook.sheet_by_index(0)
        rows = [sheet.row_values(row_index) for row_index in range(sheet.nrows)]
        return ImportedExcelSheet(
            rows,
            lambda value: xlrd.xldate.xldate_as_datetime(value, workbook.datemode),
            "xls",
        )

    def _load_xlsb_sheet(self, excel_data):
        with zipfile.ZipFile(io.BytesIO(excel_data), "r") as workbook_zip:
            shared_strings = self._read_xlsb_shared_strings(workbook_zip)
            sheet_path = self._get_first_xlsb_sheet_path(workbook_zip)
            rows = self._read_xlsb_rows(workbook_zip, sheet_path, shared_strings)
        return ImportedExcelSheet(rows, self._convert_xlsb_date, "xlsb")

    def _read_xlsb_shared_strings(self, workbook_zip):
        try:
            shared_strings_data = workbook_zip.read("xl/sharedStrings.bin")
        except KeyError:
            return []

        shared_strings = []
        for record_id, payload in XlsbRecordStream(shared_strings_data):
            if record_id == _XLSB_RECORD_SHARED_STRING:
                reader = XlsbPayloadReader(payload)
                reader.skip(1)
                shared_strings.append(reader.read_wide_string())
            elif record_id == _XLSB_RECORD_SHARED_STRINGS_END:
                break
        return shared_strings

    def _get_first_xlsb_sheet_path(self, workbook_zip):
        relationships_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.bin.rels"))
        relationships = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships_root
        }

        for record_id, payload in XlsbRecordStream(workbook_zip.read("xl/workbook.bin")):
            if record_id != _XLSB_RECORD_SHEET:
                continue

            reader = XlsbPayloadReader(payload)
            reader.skip(4)
            reader.read_uint32()
            relation_id = reader.read_wide_string()
            if relation_id not in relationships:
                continue
            return posixpath.normpath(
                posixpath.join("xl", relationships[relation_id].lstrip("/"))
            )

        raise UserError(_("No se ha encontrado ninguna hoja en el archivo Excel binario."))

    def _read_xlsb_rows(self, workbook_zip, sheet_path, shared_strings):
        sheet_data = workbook_zip.read(sheet_path)
        row_map = {}
        current_row = None
        detected_columns = 0
        highest_column = -1
        inside_sheet_data = False

        for record_id, payload in XlsbRecordStream(sheet_data):
            if record_id == _XLSB_RECORD_DIMENSION:
                reader = XlsbPayloadReader(payload)
                reader.read_uint32()
                reader.read_uint32()
                first_column = reader.read_uint32()
                last_column = reader.read_uint32()
                if first_column is not None and last_column is not None:
                    detected_columns = (last_column - first_column) + 1
                continue

            if record_id == _XLSB_RECORD_SHEETDATA:
                inside_sheet_data = True
                continue

            if record_id == _XLSB_RECORD_SHEETDATA_END:
                break

            if not inside_sheet_data:
                continue

            if record_id == _XLSB_RECORD_ROW:
                current_row = XlsbPayloadReader(payload).read_uint32()
                row_map.setdefault(current_row, {})
                continue

            if record_id in _XLSB_CELL_RECORDS and current_row is not None:
                column_index, value = self._read_xlsb_cell_value(
                    record_id,
                    payload,
                    shared_strings,
                )
                row_map.setdefault(current_row, {})[column_index] = value
                highest_column = max(highest_column, column_index)

        if not row_map:
            return []

        total_columns = max(detected_columns, highest_column + 1)
        total_rows = max(row_map) + 1
        rows = []
        for row_index in range(total_rows):
            row_values = [False] * total_columns
            for column_index, value in row_map.get(row_index, {}).items():
                row_values[column_index] = value
            rows.append(row_values)
        return rows

    def _read_xlsb_cell_value(self, record_id, payload, shared_strings):
        reader = XlsbPayloadReader(payload)
        column_index = reader.read_uint32()
        reader.read_uint32()
        value = False

        if record_id == _XLSB_RECORD_NUM:
            value = reader.read_rk_number()
        elif record_id == _XLSB_RECORD_BOOLERR:
            raw_value = reader.read_byte()
            value = hex(raw_value) if raw_value is not None else False
        elif record_id == _XLSB_RECORD_BOOL:
            value = reader.read_byte() != 0
        elif record_id == _XLSB_RECORD_FLOAT:
            value = reader.read_double()
        elif record_id == _XLSB_RECORD_STRING:
            string_index = reader.read_uint32()
            if string_index is not None and string_index < len(shared_strings):
                value = shared_strings[string_index]
        elif record_id == _XLSB_RECORD_FORMULA_STRING:
            value = reader.read_wide_string()
        elif record_id == _XLSB_RECORD_FORMULA_FLOAT:
            value = reader.read_double()
        elif record_id == _XLSB_RECORD_FORMULA_BOOL:
            value = reader.read_byte() != 0
        elif record_id == _XLSB_RECORD_FORMULA_BOOLERR:
            raw_value = reader.read_byte()
            value = hex(raw_value) if raw_value is not None else False

        return column_index, value

    def _convert_xlsb_date(self, value):
        if not isinstance(value, (int, float)):
            return None
        base_date = datetime(1899, 12, 31, 0, 0, 0)
        whole_days = int(value)
        seconds = round((value % 1) * 24 * 60 * 60)
        if whole_days == 0:
            return datetime(1900, 1, 1, 0, 0, 0) + timedelta(seconds=seconds)
        if whole_days >= 61:
            return base_date + timedelta(days=whole_days - 1, seconds=seconds)
        return base_date + timedelta(days=whole_days, seconds=seconds)

    def _normalize_text(self, value):
        if value in (False, None, ""):
            return False
        if isinstance(value, str):
            normalized = " ".join(value.replace("\xa0", " ").split())
            return normalized or False
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip() or False

    def _normalize_identifier(self, value):
        normalized = self._normalize_text(value)
        return normalized or False

    def _map_person_type(self, value):
        person_type = self._normalize_text(value)
        if not person_type:
            return False
        person_type = person_type.upper()
        if person_type == "PF":
            return "fisica"
        if person_type == "PJ":
            return "juridica"
        return False

    def _map_difficulty(self, value):
        if value in (False, None, ""):
            return False
        if isinstance(value, (int, float)):
            if int(value) == 1:
                return "simple"
            if int(value) == 2:
                return "complex"
            return False

        difficulty = self._normalize_text(value)
        if not difficulty:
            return False
        difficulty = difficulty.lower()
        if "simple" in difficulty:
            return "simple"
        if "compl" in difficulty:
            return "complex"
        return False

    def _map_state(self, value):
        state = self._normalize_text(value)
        if not state:
            return False

        state = state.lower()
        if state in self._STATE_MAPPING:
            return self._STATE_MAPPING[state]

        for key, mapped_value in self._STATE_MAPPING.items():
            if key in state:
                return mapped_value
        return False

    def _resolve_study_partner(self, person_under_study, log_messages, row_number):
        if not person_under_study:
            return False

        partner_model = self.env["res.partner"]
        study_partner = partner_model.search(
            [
                ("name", "=", person_under_study),
                ("is_study_entity", "=", True),
            ],
            limit=1,
        )
        if not study_partner:
            study_partner = partner_model.create(
                {
                    "name": person_under_study,
                    "is_study_entity": True,
                }
            )
            log_messages.append(
                f"Fila {row_number}: Contacto creado automáticamente '{person_under_study}'"
            )
        return study_partner.id

    def _resolve_partner_by_name(self, name):
        if not name:
            return False

        partner_model = self.env["res.partner"]
        partner = partner_model.search([("name", "=", name)], limit=1)
        if partner:
            return partner
        return partner_model.search([("name", "ilike", name)], limit=1)

    def _resolve_sub_cartera_partner(self, name, log_messages, row_number):
        if not name:
            return False

        partner = self._resolve_partner_by_name(name)
        if partner:
            return partner

        partner = self.env["res.partner"].create({"name": name})
        log_messages.append(
            f"Fila {row_number}: Subcartera creada automáticamente '{name}'"
        )
        return partner

    def _resolve_user_by_name(self, name):
        if not name:
            return False

        user_model = self.env["res.users"].sudo()
        user = user_model.search([("name", "=", name)], limit=1)
        if user:
            return user
        return user_model.search([("name", "ilike", name)], limit=1)

    def _read_datetime_cell(self, sheet, row_index, column_index, field_label):
        if sheet.ncols <= column_index:
            return False

        cell_value = sheet.cell_value(row_index, column_index)
        if isinstance(cell_value, (int, float)) and cell_value:
            try:
                return fields.Datetime.to_string(sheet.convert_date(cell_value))
            except (TypeError, ValueError) as error:
                _logger.warning(
                    "Error al convertir la fecha %s en fila %s: %s",
                    field_label,
                    row_index + 1,
                    error,
                )
                return False

        return self._normalize_text(cell_value)

    def _read_date_cell(self, sheet, row_index, column_index, field_label):
        if sheet.ncols <= column_index:
            return False

        cell_value = sheet.cell_value(row_index, column_index)
        if isinstance(cell_value, (int, float)) and cell_value:
            try:
                return fields.Date.to_string(sheet.convert_date(cell_value).date())
            except (AttributeError, TypeError, ValueError) as error:
                _logger.warning(
                    "Error al convertir la fecha %s en fila %s: %s",
                    field_label,
                    row_index + 1,
                    error,
                )
                return False

        return self._normalize_text(cell_value)

    def action_import_excel(self):
        self.ensure_one()
        if not self.excel_file:
            raise UserError(_("Por favor, seleccione un archivo Excel."))

        created = 0
        updated = 0
        skipped = 0
        failed = 0
        total = 0
        log_messages = []

        self.write(
            {
                "state": "draft",
                "progress": 0.0,
                "progress_text": "Iniciando importación...",
            }
        )
        self.env.cr.commit()

        try:
            excel_data = base64.b64decode(self.excel_file)
            sheet = self._load_excel_sheet(excel_data)

            if sheet.nrows < 2:
                raise UserError(_("El archivo Excel no tiene datos."))

            total_rows = sheet.nrows - 1
            self.write(
                {
                    "progress": 5.0,
                    "progress_text": f"Analizando {total_rows} registros...",
                }
            )
            self.env.cr.commit()

            sale_order_type = self.env["sale.order"]._get_expedient_sale_order_type(
                self.expedient_type
            )
            type_id_vals = sale_order_type.id if sale_order_type else False

            for row_index in range(1, sheet.nrows):
                total += 1
                try:
                    if row_index % 10 == 0 or row_index == 1:
                        progress_percent = 5.0 + ((row_index / total_rows) * 90.0)
                        self.write(
                            {
                                "progress": progress_percent,
                                "progress_text": f"Procesando registro {row_index}/{total_rows} ({int(progress_percent)}%)",
                            }
                        )
                        self.env.cr.commit()

                    analyst_name = self._normalize_text(sheet.cell_value(row_index, 0))
                    person_under_study = self._normalize_text(sheet.cell_value(row_index, 1))
                    cartera_name = self._normalize_text(sheet.cell_value(row_index, 2))
                    person_type = self._map_person_type(sheet.cell_value(row_index, 3))
                    expedient_difficulty = self._map_difficulty(sheet.cell_value(row_index, 4))
                    client_id = self._normalize_identifier(sheet.cell_value(row_index, 5))
                    expedient_number = self._normalize_identifier(sheet.cell_value(row_index, 6))

                    if not client_id or not expedient_number:
                        log_messages.append(
                            f"Fila {row_index + 1}: Omitida - Falta ID Oferta o MACRO"
                        )
                        skipped += 1
                        continue

                    person_under_study_id = self._resolve_study_partner(
                        person_under_study,
                        log_messages,
                        row_index + 1,
                    )

                    existing_order = self.env["sale.order"].search(
                        [
                            ("client_id", "=", client_id),
                            ("expedient_number", "=", expedient_number),
                        ],
                        limit=1,
                    )

                    vals = {
                        "partner_id": self.partner_id.id,
                        "client_id": client_id,
                        "expedient_number": expedient_number,
                        "expedient_type": self.expedient_type,
                        "expedient_state": "creada",
                        "person_under_study_id": person_under_study_id,
                        "person_type": person_type,
                        "deadline": "more",
                    }

                    if type_id_vals:
                        vals["type_id"] = type_id_vals

                    if expedient_difficulty:
                        vals["expedient_difficulty"] = expedient_difficulty

                    sub_cartera = self._resolve_sub_cartera_partner(
                        cartera_name,
                        log_messages,
                        row_index + 1,
                    )
                    if sub_cartera:
                        vals["sub_cartera_id"] = sub_cartera.id

                    analyst_user = self._resolve_user_by_name(analyst_name)
                    if analyst_user:
                        vals["expedient_manager_id"] = analyst_user.id
                    elif analyst_name:
                        log_messages.append(
                            f"Fila {row_index + 1}: No se encontró el analista '{analyst_name}', se usará el usuario actual"
                        )

                    date_reception = self._read_date_cell(
                        sheet, row_index, 8, "date_reception"
                    )
                    if date_reception:
                        vals["date_reception"] = date_reception

                    date_order = self._read_datetime_cell(
                        sheet, row_index, 9, "date_order"
                    )
                    if date_order:
                        vals["date_order"] = date_order

                    mapped_state = self._map_state(sheet.cell_value(row_index, 10))
                    if mapped_state:
                        vals["expedient_state"] = mapped_state

                    expedient_date_end = self._read_datetime_cell(
                        sheet, row_index, 11, "expedient_date_end"
                    )
                    if expedient_date_end:
                        vals["expedient_date_end"] = expedient_date_end

                    if existing_order:
                        existing_order.write(vals)
                        updated += 1
                        log_messages.append(
                            f"Fila {row_index + 1}: Actualizado - {client_id}/{expedient_number}"
                        )
                        continue

                    sequence_code = (
                        "sale.order.post"
                        if self.expedient_type == "post_paid"
                        else "sale.order.pre"
                    )
                    sequence = self.env["ir.sequence"].search(
                        [("code", "=", sequence_code)],
                        limit=1,
                    )
                    if sequence:
                        vals["name"] = sequence.next_by_id()

                    vals["state"] = "draft"
                    self.env["sale.order"].create(vals)
                    created += 1
                    log_messages.append(
                        f"Fila {row_index + 1}: Creado - {client_id}/{expedient_number}"
                    )
                except Exception as row_error:
                    failed += 1
                    log_messages.append(f"Fila {row_index + 1}: Error - {row_error}")
                    _logger.error("Error en fila %s: %s", row_index + 1, row_error)

            self.write(
                {
                    "progress": 100.0,
                    "progress_text": f"Importación completada: {created} creados, {updated} actualizados",
                }
            )
            self.env.cr.commit()

            self.write(
                {
                    "import_total": total,
                    "import_created": created,
                    "import_updated": updated,
                    "import_skipped": skipped,
                    "import_failed": failed,
                    "import_log": "\n".join(log_messages),
                    "state": "done",
                }
            )

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }
        except Exception as error:
            self.write(
                {
                    "progress": 0,
                    "progress_text": f"Error: {error}",
                    "state": "draft",
                }
            )
            self.env.cr.commit()
            raise UserError(_("Error al procesar el archivo Excel: %s") % error)
