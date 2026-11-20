# -*- coding: utf-8 -*-
"""Sincronizacion de adjuntos de Odoo (chatter) hacia OneDrive.

Flujo:
  1. Un adjunto asociado a un registro de un modelo configurado (por defecto
     sale.order) genera una fila ``onedrive.attachment.sync`` en estado *pending*
     (ver models/ir_attachment.py). No se hace ninguna llamada de red ahi.
  2. Un cron (``_cron_process_pending``) sube los pendientes a OneDrive en segundo
     plano, con reintentos. Odoo sigue siendo la fuente de verdad: el archivo no se
     borra de Odoo ni se borra nunca en OneDrive.

Carpeta destino:  <raiz>/<carpeta del registro>/<archivo>
  <raiz>  = onedrive_sync_folder_name de la configuracion, o "odoo".
  <carpeta del registro> = persona-client_id-expediente (ventas) o display_name.
El ID de la carpeta de cada registro se guarda en ``onedrive.folder.map`` para no
buscar por nombre (OneDrive permite renombrar y la busqueda seria fragil).
"""
import logging
import re
import urllib.parse

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GRAPH = 'https://graph.microsoft.com/v1.0'
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024   # Graph: PUT simple hasta 4 MB
CHUNK_SIZE = 320 * 1024 * 32            # 10 MiB, multiplo de 320 KiB (requisito de Graph)
MAX_ATTEMPTS = 5
CRON_BATCH = 25
CRON_LOCK_KEY = 702417002               # advisory lock: un solo cron a la vez


def _sanitize_name(name, default='SIN_NOMBRE', max_len=150):
    """Nombre valido para OneDrive (sin caracteres reservados, sin punto/espacio final)."""
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name or '').strip().rstrip('.').strip()
    if len(safe) > max_len:
        base, dot, ext = safe.rpartition('.')
        if dot and 0 < len(ext) <= 10:
            safe = base[:max_len - len(ext) - 1] + '.' + ext
        else:
            safe = safe[:max_len]
    return safe or default


class OneDriveFolderMap(models.Model):
    _name = 'onedrive.folder.map'
    _description = 'Carpeta de OneDrive asociada a un registro de Odoo'

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    folder_item_id = fields.Char('ID de carpeta en OneDrive', required=True)
    folder_path = fields.Char('Ruta')

    _sql_constraints = [
        ('record_unique', 'unique(res_model, res_id)',
         'Ya existe una carpeta asociada a este registro.'),
    ]


class OneDriveAttachmentSync(models.Model):
    _name = 'onedrive.attachment.sync'
    _description = 'Adjunto de Odoo sincronizado con OneDrive'
    _order = 'id desc'

    attachment_id = fields.Many2one('ir.attachment', 'Adjunto', required=True, ondelete='cascade', index=True)
    name = fields.Char('Nombre', readonly=True)
    res_model = fields.Char('Modelo', readonly=True, index=True)
    res_id = fields.Integer('ID del registro', readonly=True)
    record_name = fields.Char('Registro', readonly=True)
    file_size = fields.Float('Tamaño (bytes)', digits=(16, 0), readonly=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('done', 'Subido'),
        ('error', 'Error'),
        ('skipped', 'Omitido'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer('Intentos', default=0, readonly=True)
    last_error = fields.Text('Último error', readonly=True)
    onedrive_item_id = fields.Char('ID en OneDrive', readonly=True)
    web_url = fields.Char('Enlace OneDrive', readonly=True)
    onedrive_path = fields.Char('Ruta en OneDrive', readonly=True)
    date_synced = fields.Datetime('Fecha de subida', readonly=True)

    _sql_constraints = [
        ('attachment_unique', 'unique(attachment_id)',
         'Este adjunto ya esta en la cola de sincronizacion.'),
    ]

    # ------------------------------------------------------------------
    # Encolado (sin red)
    # ------------------------------------------------------------------
    @api.model
    def _get_sync_settings(self):
        settings = self.env['onedrive.settings'].sudo().search([], limit=1)
        if not settings or not settings.attachment_sync_enabled:
            return None
        return settings

    @api.model
    def _enqueue_attachments(self, attachments):
        """Crea filas pendientes para los adjuntos que cumplan las reglas."""
        settings = self._get_sync_settings()
        if not settings:
            return
        sync_models = settings._get_attachment_sync_models()
        todo = attachments.sudo().filtered(
            lambda a: a.res_model in sync_models and a.res_id
            and not a.res_field and a.type == 'binary')
        if not todo:
            return
        existing = self.sudo().search([('attachment_id', 'in', todo.ids)]).attachment_id
        for att in todo - existing:
            record = self.env[att.res_model].sudo().browse(att.res_id).exists()
            self.sudo().create({
                'attachment_id': att.id,
                'name': att.name,
                'res_model': att.res_model,
                'res_id': att.res_id,
                'record_name': record.display_name if record else False,
                'file_size': att.file_size,
            })

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_process_pending(self, limit=CRON_BATCH):
        settings = self._get_sync_settings()
        if not settings:
            return {'processed': 0, 'done': 0, 'failed': 0}
        cr = self.env.cr
        cr.execute('SELECT pg_try_advisory_lock(%s)', (CRON_LOCK_KEY,))
        if not cr.fetchone()[0]:
            _logger.info('[OneDrive adjuntos] otro proceso ya esta subiendo adjuntos')
            return {'processed': 0, 'done': 0, 'failed': 0}
        stats = {'processed': 0, 'done': 0, 'failed': 0}
        try:
            try:
                token = self.env['onedrive.service']._get_token()
            except Exception as e:
                _logger.warning('[OneDrive adjuntos] no se pudo obtener token: %s', e)
                return stats
            pending = self.sudo().search(
                [('state', '=', 'pending'), ('attempts', '<', MAX_ATTEMPTS)],
                order='attempts, id', limit=limit)
            for rec in pending:
                stats['processed'] += 1
                try:
                    with cr.savepoint():
                        rec._process_one(token, settings)
                    stats['done'] += 1
                except Exception as e:  # noqa: BLE001 - cualquier fallo se reintenta
                    stats['failed'] += 1
                    rec._mark_failed(e)
                cr.commit()
                self.env.invalidate_all()
        finally:
            try:
                cr.execute('SELECT pg_advisory_unlock(%s)', (CRON_LOCK_KEY,))
            except Exception:
                _logger.warning('[OneDrive adjuntos] no se pudo liberar el lock (se libera al cerrar la conexion)')
        _logger.info('[OneDrive adjuntos] procesados=%(processed)s ok=%(done)s fallidos=%(failed)s', stats)
        return stats

    def _mark_failed(self, error):
        self.ensure_one()
        attempts = self.attempts + 1
        _logger.warning('[OneDrive adjuntos] fallo subiendo %s (intento %s): %s', self.name, attempts, error)
        self.write({
            'attempts': attempts,
            'last_error': str(error)[:2000],
            'state': 'error' if attempts >= MAX_ATTEMPTS else 'pending',
        })

    def action_retry(self):
        self.filtered(lambda r: r.state in ('error', 'skipped')).write(
            {'state': 'pending', 'attempts': 0, 'last_error': False})

    # ------------------------------------------------------------------
    # Subida de un adjunto
    # ------------------------------------------------------------------
    def _process_one(self, token, settings):
        self.ensure_one()
        att = self.attachment_id
        max_bytes = (settings.attachment_sync_max_mb or 50) * 1024 * 1024
        if att.file_size and att.file_size > max_bytes:
            self.write({'state': 'skipped',
                        'last_error': _('Supera el tamaño máximo (%s MB)') % settings.attachment_sync_max_mb})
            return
        record = self.env[att.res_model].sudo().browse(att.res_id).exists() if att.res_model else None
        if not record:
            self.write({'state': 'skipped', 'last_error': _('El registro ya no existe')})
            return
        raw = att.raw
        if not raw:
            self.write({'state': 'skipped', 'last_error': _('Adjunto vacío')})
            return

        file_name = _sanitize_name(att.name, default='adjunto_%s' % att.id)
        folder_id, cached = self._get_record_folder(token, settings, record)
        try:
            item = self._upload(token, folder_id, file_name, raw)
        except _FolderMissing:
            if not cached:
                raise
            # La carpeta cacheada ya no existe en OneDrive: se recrea y se reintenta una vez.
            self.env['onedrive.folder.map'].sudo().search(
                [('res_model', '=', record._name), ('res_id', '=', record.id)]).unlink()
            folder_id, _cached = self._get_record_folder(token, settings, record)
            item = self._upload(token, folder_id, file_name, raw)

        path = self.env['onedrive.folder.map'].sudo().search(
            [('res_model', '=', record._name), ('res_id', '=', record.id)], limit=1).folder_path
        self.write({
            'state': 'done',
            'onedrive_item_id': item.get('id'),
            'web_url': item.get('webUrl'),
            'onedrive_path': '%s/%s' % (path or '', item.get('name') or file_name),
            'date_synced': fields.Datetime.now(),
            'last_error': False,
            'record_name': record.display_name,
        })

    # ------------------------------------------------------------------
    # Carpetas
    # ------------------------------------------------------------------
    # Carpeta de modelo (nivel intermedio) para los modelos que no son ventas.
    MODEL_FOLDER_LABELS = {
        'res.partner': 'Contactos',
        'account.payment': 'Pagos',
        'purchase.order': 'Compras',
        'stock.picking': 'Albaranes',
    }
    MOVE_TYPE_FOLDER_LABELS = {
        'out_invoice': 'Facturas de cliente',
        'out_refund': 'Facturas de cliente',
        'out_receipt': 'Facturas de cliente',
        'in_invoice': 'Facturas de proveedor',
        'in_refund': 'Facturas de proveedor',
        'in_receipt': 'Facturas de proveedor',
        'entry': 'Asientos',
    }

    @api.model
    def _get_record_folder_segments(self, record):
        """Ruta de carpetas bajo la raiz: [..., carpeta del registro].

        - sale.order: <persona>-<client_id>-<expediente> (o el nombre del pedido).
        - account.move: <Facturas de cliente|Facturas de proveedor|Asientos>/<numero>
        - res.partner: Contactos/<nombre> (<id>)
        - resto: <etiqueta del modelo>/<nombre del registro>
        """
        model = record._name
        if model == 'sale.order':
            person = getattr(record, 'person_under_study_id', False)
            parts = [
                person.name if person else '',
                getattr(record, 'client_id', '') or '',
                getattr(record, 'expedient_number', '') or '',
            ]
            name = '-'.join(str(p).strip() for p in parts if p and str(p).strip())
            return [_sanitize_name(name or record.display_name, default='sale_order_%s' % record.id)]
        if model == 'account.move':
            label = self.MOVE_TYPE_FOLDER_LABELS.get(record.move_type, 'Asientos')
            number = record.name if record.name and record.name != '/' else 'Borrador-%s' % record.id
            return [label, _sanitize_name(number, default='asiento_%s' % record.id)]
        if model == 'res.partner':
            # Los contactos repiten nombre con frecuencia: el id evita que dos compartan carpeta.
            name = '%s (%s)' % (record.display_name or record.name or 'contacto', record.id)
            return [self.MODEL_FOLDER_LABELS[model], _sanitize_name(name, default='contacto_%s' % record.id)]
        label = self.MODEL_FOLDER_LABELS.get(model) or record._description or model
        return [_sanitize_name(label), _sanitize_name(record.display_name, default='%s_%s' % (model, record.id))]

    def _get_record_folder(self, token, settings, record):
        """Devuelve (id_carpeta, desde_cache). Renombra la carpeta si el registro cambio de nombre."""
        FolderMap = self.env['onedrive.folder.map'].sudo()
        segments = self._get_record_folder_segments(record)
        root_name = _sanitize_name(settings.onedrive_sync_folder_name or 'odoo')
        expected_path = '/'.join([root_name] + segments)
        mapped = FolderMap.search([('res_model', '=', record._name), ('res_id', '=', record.id)], limit=1)
        if mapped:
            current_name = (mapped.folder_path or '').rsplit('/', 1)[-1]
            if current_name != segments[-1]:
                self._rename_folder(token, mapped, segments[-1])
            return mapped.folder_item_id, True
        parent_id = self._ensure_folder(token, root_name, None)
        for segment in segments:
            parent_id = self._ensure_folder(token, segment, parent_id)
        FolderMap.create({
            'res_model': record._name,
            'res_id': record.id,
            'folder_item_id': parent_id,
            'folder_path': expected_path,
        })
        return parent_id, False

    def _rename_folder(self, token, mapped, new_name):
        """Renombra la carpeta de un registro (p. ej. factura: Borrador-12 -> INV/2026/0001).
        Si falla (nombre ya usado, permisos...) se deja el nombre antiguo y se sigue."""
        try:
            resp = self._graph('PATCH', '%s/me/drive/items/%s' % (GRAPH, mapped.folder_item_id), token, json={
                'name': new_name, '@microsoft.graph.conflictBehavior': 'fail'})
            if resp.status_code == 200:
                parent_path = (mapped.folder_path or '').rsplit('/', 1)[0]
                mapped.folder_path = '%s/%s' % (parent_path, new_name) if parent_path else new_name
            else:
                _logger.warning('[OneDrive adjuntos] no se pudo renombrar la carpeta a "%s": %s %s',
                                new_name, resp.status_code, resp.text[:200])
        except Exception as e:  # noqa: BLE001
            _logger.warning('[OneDrive adjuntos] error renombrando carpeta a "%s": %s', new_name, e)

    # ------------------------------------------------------------------
    # Llamadas a Microsoft Graph
    # ------------------------------------------------------------------
    @staticmethod
    def _graph(method, url, token, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = 'Bearer %s' % token
        kwargs.setdefault('timeout', 60)
        return requests.request(method, url, headers=headers, **kwargs)

    @staticmethod
    def _item_base(parent_id):
        return '%s/me/drive/%s' % (GRAPH, 'items/%s' % parent_id if parent_id else 'root')

    def _ensure_folder(self, token, name, parent_id):
        base = self._item_base(parent_id)
        path_url = '%s:/%s' % (base, urllib.parse.quote(name, safe=''))
        resp = self._graph('GET', path_url, token)
        if resp.status_code == 200:
            item = resp.json()
            if item.get('folder') is None:
                raise UserError(_('En OneDrive existe un archivo (no carpeta) llamado "%s"') % name)
            return item['id']
        if resp.status_code != 404:
            raise UserError(_('Error consultando carpeta "%s": %s %s') % (name, resp.status_code, resp.text[:300]))
        resp = self._graph('POST', '%s/children' % base, token, json={
            'name': name, 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail'})
        if resp.status_code in (200, 201):
            return resp.json()['id']
        if resp.status_code == 409:  # otra ejecucion la creo entre medias
            resp = self._graph('GET', path_url, token)
            if resp.status_code == 200:
                return resp.json()['id']
        raise UserError(_('No se pudo crear la carpeta "%s": %s %s') % (name, resp.status_code, resp.text[:300]))

    def _upload(self, token, folder_id, file_name, raw):
        quoted = urllib.parse.quote(file_name, safe='')
        item_path = '%s/me/drive/items/%s:/%s' % (GRAPH, folder_id, quoted)

        # Idempotencia: si un intento anterior subio el archivo pero se corto antes
        # de guardar el resultado, se adopta el existente (mismo nombre y tamaño).
        resp = self._graph('GET', item_path, token)
        if resp.status_code == 200:
            item = resp.json()
            if item.get('file') is not None and item.get('size') == len(raw):
                return item

        if len(raw) <= SIMPLE_UPLOAD_LIMIT:
            resp = self._graph(
                'PUT', '%s:/content?@microsoft.graph.conflictBehavior=rename' % item_path, token,
                data=raw, headers={'Content-Type': 'application/octet-stream'})
            if resp.status_code in (200, 201):
                return resp.json()
            if resp.status_code == 404:
                raise _FolderMissing()
            raise UserError(_('Error subiendo "%s": %s %s') % (file_name, resp.status_code, resp.text[:300]))
        return self._upload_large(token, item_path, file_name, raw)

    def _upload_large(self, token, item_path, file_name, raw):
        """Sesion de subida por trozos (archivos > 4 MB)."""
        resp = self._graph('POST', '%s:/createUploadSession' % item_path, token, json={
            'item': {'@microsoft.graph.conflictBehavior': 'rename', 'name': file_name}})
        if resp.status_code == 404:
            raise _FolderMissing()
        if resp.status_code != 200:
            raise UserError(_('No se pudo abrir la sesión de subida de "%s": %s %s')
                            % (file_name, resp.status_code, resp.text[:300]))
        upload_url = resp.json()['uploadUrl']
        total = len(raw)
        start = 0
        while start < total:
            chunk = raw[start:start + CHUNK_SIZE]
            end = start + len(chunk) - 1
            # La uploadUrl esta pre-autenticada: no se envia Authorization.
            resp = requests.put(upload_url, data=chunk, timeout=300, headers={
                'Content-Length': str(len(chunk)),
                'Content-Range': 'bytes %s-%s/%s' % (start, end, total),
            })
            if resp.status_code in (200, 201):
                return resp.json()
            if resp.status_code != 202:
                try:
                    requests.delete(upload_url, timeout=30)
                except Exception:
                    pass
                raise UserError(_('Error subiendo "%s" (bytes %s-%s): %s %s')
                                % (file_name, start, end, resp.status_code, resp.text[:300]))
            start = end + 1
        raise UserError(_('La subida de "%s" terminó sin confirmación de OneDrive') % file_name)


class _FolderMissing(Exception):
    """La carpeta destino no existe (borrada en OneDrive)."""
