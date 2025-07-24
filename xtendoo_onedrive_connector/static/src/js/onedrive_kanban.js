/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";

patch(KanbanController.prototype, "onedrive_kanban", {
    /**
     * Setup event listeners for OneDrive kanban view
     */
    setup() {
        this._super(...arguments);
        this._setupOneDriveEvents();
    },

    /**
     * Setup OneDrive specific event listeners
     */
    _setupOneDriveEvents() {
        if (this.props.resModel !== 'onedrive.document') {
            return;
        }

        // Event listener for folder open buttons
        this.el.addEventListener('click', (event) => {
            if (event.target.closest('.o_kanban_folder_open')) {
                this._onFolderOpen(event);
            } else if (event.target.closest('.o_kanban_file_download')) {
                this._onFileDownload(event);
            }
        });
    },

    /**
     * Handle folder open action
     */
    async _onFolderOpen(event) {
        event.stopPropagation();
        event.preventDefault();

        const button = event.target.closest('.o_kanban_folder_open');
        const folderId = button.getAttribute('data-folder-id');

        if (!folderId) {
            return;
        }

        // Navigate to show only children of this folder
        await this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Documentos OneDrive',
            res_model: 'onedrive.document',
            view_mode: 'kanban,tree,form',
            views: [[false, 'kanban'], [false, 'tree'], [false, 'form']],
            domain: [['parent_id', '=', parseInt(folderId)]],
            context: {
                'default_parent_id': parseInt(folderId),
                'breadcrumb_parent_id': parseInt(folderId)
            },
            target: 'current',
        });
    },

    /**
     * Handle file download action
     */
    _onFileDownload(event) {
        event.stopPropagation();
        event.preventDefault();

        const button = event.target.closest('.o_kanban_file_download');
        const fileUrl = button.getAttribute('data-file-url');

        if (!fileUrl) {
            return;
        }

        // Open file in new tab/window for download
        window.open(fileUrl, '_blank');
    }
});
