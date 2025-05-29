/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { FormStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";

// Patch to make status bar field editable
patch(StatusBarField.prototype, {
    async _onClickStatus(ev) {
        const result = await this._super(...arguments);
        // Force re-render in case the click handler didn't properly trigger an update
        this.render(true);
        return result;
    }
});

// Fix for status bar widget in expedients
patch(FormStatusIndicator.prototype, {
    get isDisabled() {
        // Don't disable the status bar for expedient records
        if (this.props.record && this.props.record.data.expedient_type && this.props.record.data.expedient_type !== 'none') {
            return false;
        }
        // Otherwise use the original behavior
        return this._super(...arguments);
    }
});
