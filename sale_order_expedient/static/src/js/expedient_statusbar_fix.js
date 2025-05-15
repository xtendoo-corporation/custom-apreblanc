/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";

patch(StatusBarField.prototype, {
    async _onClickStatus(ev) {
        const result = await this._super(...arguments);
        // Force re-render in case the click handler didn't properly trigger an update
        this.render(true);
        return result;
    }
});
