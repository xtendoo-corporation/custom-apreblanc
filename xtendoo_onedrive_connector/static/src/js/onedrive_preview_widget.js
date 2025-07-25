/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OneDrivePreviewWidget extends Component {
    setup() {
        this.state = useState({
            previewUrl: null,
            fileType: null,
            isLoading: true,
            hasError: false
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
        const isFolder = record.data.is_folder;

        this.state.isLoading = false;
        this.state.hasError = false;

        if (!fileUrl || isFolder) {
            this.state.previewUrl = null;
            this.state.fileType = null;
            return;
        }

        // Convertir URL de OneDrive para previsualización
        let previewUrl = fileUrl;

        if (fileUrl.includes('sharepoint.com') || fileUrl.includes('onedrive.live.com')) {
            if (fileUrl.includes('?download=1')) {
                previewUrl = fileUrl.replace('?download=1', '?embed=1');
            } else if (fileUrl.includes('view.aspx')) {
                previewUrl = fileUrl + '&action=embedview';
            }
        }

        this.state.previewUrl = previewUrl;
        this.state.fileType = fileType?.toLowerCase() || '';
    }

    get canPreview() {
        if (!this.state.previewUrl) return false;

        const previewableTypes = [
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
            'txt', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'
        ];

        return previewableTypes.some(type =>
            this.state.fileType.includes(type) ||
            this.state.previewUrl.toLowerCase().includes(`.${type}`)
        );
    }

    onIframeError() {
        this.state.hasError = true;
    }
}

OneDrivePreviewWidget.template = "xtendoo_onedrive_connector.OneDrivePreviewWidget";

registry.category("fields").add("onedrive_preview", OneDrivePreviewWidget);
