# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from odoo.addons.xtendoo_onedrive_connector.models import onedrive_attachment_sync as mod
from odoo.addons.xtendoo_onedrive_connector.models.onedrive_service import OneDriveService


class _Resp:
    def __init__(self, code, data=None):
        self.status_code, self._data, self.text = code, data or {}, str(data or {})

    def json(self):
        return self._data


@tagged('post_install', '-at_install')
class TestAttachmentPreview(HttpCase):
    """Vista previa incrustada (Graph /preview) con Graph simulado y navegador real."""

    def setUp(self):
        super().setUp()
        group = self.env.ref('base.group_system')
        self.env['res.users'].create({
            'name': 'OneDrive tester', 'login': 'onedrive_tester', 'password': 'onedrive_tester',
            'groups_id': [(6, 0, [group.id, self.env.ref('base.group_user').id])],
        })
        partner = self.env['res.partner'].create({'name': 'Preview test'})
        att = self.env['ir.attachment'].create({
            'name': 'informe.pdf', 'raw': b'%PDF-1.4 test', 'type': 'binary',
            'res_model': 'res.partner', 'res_id': partner.id})
        Sync = self.env['onedrive.attachment.sync']
        self.sync = Sync.search([('attachment_id', '=', att.id)]) or Sync.create({
            'attachment_id': att.id, 'name': att.name, 'res_model': 'res.partner', 'res_id': partner.id})
        self.sync.write({'state': 'done', 'onedrive_item_id': 'ITEM-1', 'web_url': 'https://onedrive.example/ITEM-1'})
        self.form_url = '/web#model=onedrive.attachment.sync&id=%d&view_type=form' % self.sync.id

    def test_build_html_get_url(self):
        html = self.env['onedrive.attachment.sync']._build_preview_html({'getUrl': 'https://x/y?a=1&b="2"'})
        self.assertIn('<iframe src="https://x/y?a=1&amp;b=&quot;2&quot;"', html)

    def test_build_html_post_url(self):
        html = self.env['onedrive.attachment.sync']._build_preview_html(
            {'postUrl': 'https://x/post', 'postParameters': 'access_token=abc&x=1'})
        self.assertIn('srcdoc=', html)
        self.assertIn('name=&quot;access_token&quot;', html)
        self.assertFalse(self.env['onedrive.attachment.sync']._build_preview_html({}))

    def _graph(self, status, data):
        calls = []

        def fake_request(method, url, **kw):
            calls.append((method, url))
            return _Resp(status, data)
        return fake_request, calls

    # Script del navegador: pulsa "Vista previa" y espera al resultado en el dialogo.
    _JS_WAIT = """
        const wait = (sel, ms = 20000) => new Promise((resolve, reject) => {
            const t0 = Date.now();
            const timer = setInterval(() => {
                const el = document.querySelector(sel);
                if (el) { clearInterval(timer); resolve(el); }
                else if (Date.now() - t0 > ms) { clearInterval(timer); reject(new Error("timeout esperando " + sel)); }
            }, 200);
        });
    """

    def _run_browser(self, check_js):
        code = self._JS_WAIT + """
        (async () => {
            try {
                (await wait(".o_form_view button[name='action_preview']")).click();
                %s
                console.log("test successful");
            } catch (e) { console.error("FALLO: " + e.message); }
        })();
        """ % check_js
        self.browser_js(self.form_url, code, ready="odoo.isReady", login='onedrive_tester', timeout=120)

    def test_preview_dialog_shows_iframe(self):
        fake, calls = self._graph(200, {'getUrl': '/web/static/img/logo.png'})
        check = """
                const frame = await wait(".o_dialog .o_onedrive_preview iframe");
                if (!frame.getAttribute("src").includes("/web/static/img/logo.png")) {
                    throw new Error("src inesperado: " + frame.getAttribute("src"));
                }
                if (document.querySelector(".o_dialog .alert-warning")) {
                    throw new Error("no deberia haber aviso cuando hay vista previa");
                }
        """
        with patch.object(mod.requests, 'request', fake), patch.object(OneDriveService, '_get_token', lambda s: 'tok'):
            self._run_browser(check)
        self.assertTrue(any(m == 'POST' and u.endswith('/me/drive/items/ITEM-1/preview') for m, u in calls), calls)

    def test_preview_dialog_unsupported(self):
        fake, _calls = self._graph(415, {'error': {'code': 'notSupported'}})
        check = """
                await wait(".o_dialog .alert-warning");
                if (document.querySelector(".o_dialog iframe")) {
                    throw new Error("no deberia haber iframe cuando no hay vista previa");
                }
        """
        with patch.object(mod.requests, 'request', fake), patch.object(OneDriveService, '_get_token', lambda s: 'tok'):
            self._run_browser(check)

    def test_preview_requires_uploaded(self):
        self.sync.state = 'pending'
        with self.assertRaises(Exception):
            self.sync.action_preview()


@tagged('post_install', '-at_install')
class TestDocumentPreview(HttpCase):
    """Vista previa y 'Ver en OneDrive' en la lista de Documentos OneDrive (onedrive.document)."""

    def setUp(self):
        super().setUp()
        group = self.env.ref('base.group_system')
        self.env['res.users'].create({
            'name': 'OneDrive tester 2', 'login': 'onedrive_tester2', 'password': 'onedrive_tester2',
            'groups_id': [(6, 0, [group.id, self.env.ref('base.group_user').id])],
        })
        Doc = self.env['onedrive.document']
        self.doc = Doc.create({'name': 'contrato_prueba.docx', 'onedrive_id': 'ITEM-DOC-1',
                               'file_url': 'https://download.example/x', 'is_folder': False})
        self.folder = Doc.create({'name': 'carpeta_prueba', 'onedrive_id': 'ITEM-FOLDER', 'is_folder': True})
        self.nofile = Doc.create({'name': 'manual_prueba.docx'})

    def test_open_onedrive_fetches_and_stores_web_url(self):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _Resp(200, {'webUrl': 'https://tenant.sharepoint.com/doc1'})
        with patch('odoo.addons.xtendoo_onedrive_connector.models.onedrive_document.requests.get', fake_get), \
                patch.object(OneDriveService, '_get_token', lambda s: 'tok'):
            action = self.doc.action_open_onedrive()
            self.assertEqual(action['url'], 'https://tenant.sharepoint.com/doc1')
            self.assertEqual(self.doc.web_url, 'https://tenant.sharepoint.com/doc1')
            self.doc.action_open_onedrive()  # segunda vez: usa el guardado, sin red
        self.assertEqual(len(calls), 1)

    def test_open_onedrive_requires_onedrive_id(self):
        with self.assertRaises(Exception):
            self.nofile.action_open_onedrive()

    def test_preview_rejects_folders_and_local_docs(self):
        for rec in (self.folder, self.nofile):
            with self.assertRaises(Exception):
                rec.action_preview()

    def test_preview_returns_dialog_action(self):
        calls = []

        def fake_request(method, url, **kw):
            calls.append((method, url))
            return _Resp(200, {'getUrl': 'https://preview.example/embed'})
        with patch.object(mod.requests, 'request', fake_request), patch.object(OneDriveService, '_get_token', lambda s: 'tok'):
            action = self.doc.action_preview()
        self.assertEqual(action['res_model'], 'onedrive.attachment.preview')
        self.assertTrue(any(u.endswith('/me/drive/items/ITEM-DOC-1/preview') for _m, u in calls))
        wizard = self.env['onedrive.attachment.preview'].browse(action['res_id'])
        self.assertIn('https://preview.example/embed', wizard.preview_html)

    def test_list_buttons_in_browser(self):
        """En la lista: ojo y 'ver en OneDrive' en archivos; ninguno en carpetas ni docs locales;
        al pulsar el ojo se abre el dialogo con el iframe."""
        def fake_request(method, url, **kw):
            return _Resp(200, {'getUrl': '/web/static/img/logo.png'})
        code = TestAttachmentPreview._JS_WAIT + """
        (async () => {
            try {
                const input = await wait(".o_searchview_input");
                input.value = "_prueba";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
                await wait(".o_list_view .o_data_row");
                await new Promise((r) => setTimeout(r, 1500));
                const rows = [...document.querySelectorAll(".o_list_view .o_data_row")];
                const rowOf = (txt) => rows.find((r) => r.textContent.includes(txt));
                const file = rowOf("contrato_prueba.docx"), folder = rowOf("carpeta_prueba"), local = rowOf("manual_prueba.docx");
                if (!file || !folder || !local) throw new Error("faltan filas de prueba");
                if (!file.querySelector("button[name='action_preview']")) throw new Error("archivo sin boton de vista previa");
                if (!file.querySelector("button[name='action_open_onedrive']")) throw new Error("archivo sin boton ver en OneDrive");
                if (folder.querySelector("button[name='action_preview']")) throw new Error("la carpeta no deberia tener vista previa");
                if (!folder.querySelector("button[name='action_open_onedrive']")) throw new Error("la carpeta deberia poder verse en OneDrive");
                if (local.querySelector("button[name='action_preview']") || local.querySelector("button[name='action_open_onedrive']")) {
                    throw new Error("un documento local no deberia tener botones de OneDrive");
                }
                file.querySelector("button[name='action_preview']").click();
                const frame = await wait(".o_dialog .o_onedrive_preview iframe");
                if (!frame.getAttribute("src").includes("/web/static/img/logo.png")) throw new Error("src inesperado");
                console.log("test successful");
            } catch (e) { console.error("FALLO: " + e.message); }
        })();
        """
        with patch.object(mod.requests, 'request', fake_request), patch.object(OneDriveService, '_get_token', lambda s: 'tok'):
            self.browser_js('/web#action=xtendoo_onedrive_connector.action_onedrive_document', code,
                            ready="odoo.isReady", login='onedrive_tester2', timeout=120)
