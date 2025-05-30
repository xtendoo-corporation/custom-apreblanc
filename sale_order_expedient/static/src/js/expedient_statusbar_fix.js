/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { FormStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";
import { StatusBar } from "@web/views/fields/status_bar/status_bar";

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

patch(StatusBar.prototype, {
    async onSelectionChange(ev) {
        // If it's our expedient statusbar
        if (this.props.record &&
            (this.props.name === "expedient_state" ||
             this.props.className === "expedient_statusbar")) {

            const newValue = ev.target.value;
            const actionMapping = {
                'creada': false, // No action for initial state
                'pendiente_documentacion': 'action_expedient_pendiente_documentacion',
                'aprobada': 'action_expedient_aprobada',
                'rechazada': 'action_expedient_rechazada',
                'cancelada': 'action_expedient_cancelada',
            };

            // Get the corresponding action method
            const actionMethod = actionMapping[newValue];

            if (actionMethod) {
                // Use the action method directly
                await this.props.record.model.orm.call(
                    this.props.record.resModel,
                    actionMethod,
                    [this.props.record.resId],
                    {}
                );

                // Reload the record to update the UI
                await this.props.record.load();
                return;
            }
        }

        // Call the original method for other statusbars
        return this._super(...arguments);
    }
});
