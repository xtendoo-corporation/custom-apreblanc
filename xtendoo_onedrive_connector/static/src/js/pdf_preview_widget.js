/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class PdfPreviewWidget extends Component {
    get pdfUrl() {
        const recordId = this.props.record.data.id;
        return recordId ? `/onedrive/pdf/${recordId}` : '';
    }
}

PdfPreviewWidget.template = "xtendoo_onedrive_connector.PdfPreviewWidget";

registry.category("fields").add("pdf_preview", PdfPreviewWidget);
