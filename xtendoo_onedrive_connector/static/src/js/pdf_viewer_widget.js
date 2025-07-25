/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class PdfViewerWidget extends Component {
    get pdfUrl() {
        const recordId = this.props.record.data.id;
        return recordId ? `/web/content?field=file_data&model=onedrive.document&id=${recordId}` : '';
    }
}

PdfViewerWidget.template = "xtendoo_onedrive_connector.PdfViewerWidget";

registry.category("fields").add("pdf_viewer_simple", PdfViewerWidget);
