/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";

export class OneDrivePreviewWidget extends Component {
    setup() {
        this.state = useState({
            previewUrl: null,
            downloadUrl: null,
            fileType: null,
            fileName: null,
            isLoading: true,
            hasError: false,
            canEmbedPreview: false
        });

        onWillStart(async () => {
            this.updatePreview();
        });

        onWillUpdateProps(async (nextProps) => {
            this.updatePreview(nextProps);
        });
    }

    updatePreview(props = this.props) {
        const record = props.record;
        const fileUrl = record.data.file_url;
        const fileType = record.data.file_type;
        const fileName = record.data.name;
        const isFolder = record.data.is_folder;
        const recordId = record.data.id;

        this.state.isLoading = false;
        this.state.hasError = false;
        this.state.fileName = fileName;
        this.state.fileType = fileType?.toLowerCase() || '';

        if (!fileUrl || isFolder || !recordId) {
            this.state.previewUrl = null;
            this.state.downloadUrl = null;
            this.state.canEmbedPreview = false;
            return;
        }

        // URLs usando nuestro controlador proxy
        this.state.previewUrl = `/onedrive/preview/${recordId}`;
        this.state.downloadUrl = `/onedrive/download/${recordId}`;

        // Determinar si el archivo se puede previsualizar en iframe
        const previewableTypes = [
            'pdf', 'txt', 'csv',
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'
        ];

        this.state.canEmbedPreview = previewableTypes.some(type =>
            this.state.fileType.includes(type) ||
            fileName?.toLowerCase().includes(`.${type}`)
        );
    }

    onIframeError() {
        this.state.hasError = true;
    }

    openInNewWindow() {
        if (this.state.previewUrl) {
            window.open(this.state.previewUrl, '_blank');
        }
    }

    downloadFile() {
        if (this.state.downloadUrl) {
            window.open(this.state.downloadUrl, '_blank');
        }
    }
}

OneDrivePreviewWidget.template = "xtendoo_onedrive_connector.OneDrivePreviewWidget";

registry.category("fields").add("onedrive_preview", OneDrivePreviewWidget);
