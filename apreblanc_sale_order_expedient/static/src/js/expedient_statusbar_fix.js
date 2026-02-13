/** @odoo-module **/

import { registry } from "@web/core/registry";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";
// Removing invalid import of StatusBar
// import { StatusBar } from "@web/views/fields/status_bar/status_bar";

// Patch to handle status bar field logic
patch(StatusBarField.prototype, {
    async selectItem(item) {
        // If it's our expedient statusbar
        if (this.props.record && this.props.name === "expedient_state") {
            const newValue = item.value;
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

        // Call the original method
        return this._super(...arguments);
    }
});
