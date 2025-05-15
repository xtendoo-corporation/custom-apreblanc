/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

// Guardar referencias a los métodos originales antes del patch
const originalSetup = ListController.prototype.setup;
const originalCreateRecord = ListController.prototype.createRecord;

patch(ListController.prototype, {
    setup() {
        // Llamar al método original en lugar de usar _super
        originalSetup.call(this, ...arguments);
        this.action = useService("action");
    },

    async createRecord() {
        // Verificamos si estamos en sale.order Y es un expediente
        // Revisamos el contexto para determinar si estamos en expedientes
        const isExpedientView = this.props.context &&
                               (this.props.context.default_is_expedient ||
                                this.props.context.search_default_is_expedient ||
                                this.props.context.expedient_mode);

        if (this.props.resModel === 'sale.order' && isExpedientView) {
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Crear Nuevo Expediente',
                res_model: 'expedient.create.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: this.props.context || {},
            });
        } else {
            // Para otros modelos, comportamiento estándar
            await originalCreateRecord.call(this, ...arguments);
        }
    },
});
