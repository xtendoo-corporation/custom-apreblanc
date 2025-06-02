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
        // Verificamos si estamos en sale.order
        if (this.props.resModel === 'sale.order') {
            console.log("Interceptando creación en sale.order", this.props.context);

            // Verificamos si estamos en la vista de expedientes
            const isExpedientView = this._isExpedientView();

            if (isExpedientView) {
                console.log("Detectada vista de expedientes, lanzando wizard");
                // Lanzar el wizard de expediente
                await this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Crear Nuevo Expediente',
                    res_model: 'expedient.create.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: this.props.context || {},
                });
                return;
            }
        }

        // Para otros modelos, comportamiento estándar
        await originalCreateRecord.call(this, ...arguments);
    },

    _isExpedientView() {
        const context = this.props.context || {};

        // Si la flag expedient_mode está presente, estamos en la vista de expedientes
        if (context.expedient_mode) {
            console.log("Detectado expedient_mode en contexto");
            return true;
        }

        // También verificamos las otras flags por compatibilidad
        if (context.default_is_expedient ||
            context.search_default_is_expedient ||
            context.default_expedient_type ||
            context.search_default_expedient_filter) {
            console.log("Detectadas otras flags de expedientes en contexto");
            return true;
        }

        return false;
    }
});
