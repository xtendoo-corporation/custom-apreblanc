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
        // Verificamos si estamos en sale.order o pre.paid.expedient
        if (this.props.resModel === 'sale.order' || this.props.resModel === 'pre.paid.expedient') {
            console.log("Interceptando creación en " + this.props.resModel, this.props.context);

            // Verificamos si estamos en la vista de expedientes
            const isExpedientView = this._isExpedientView();
            const isPrepaidView = this._isPrepaidView();

            if (isExpedientView) {
                console.log("Detectada vista de expedientes postpago, lanzando wizard");
                // Lanzar el wizard de expediente postpago
                await this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Crear Nuevo Expediente Postpago',
                    res_model: 'expedient.create.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {...this.props.context, 'default_expedient_type': 'post_paid'},
                });
                return;
            } else if (isPrepaidView) {
                console.log("Detectada vista de expedientes prepagados, lanzando wizard");
                // Lanzar el wizard específico para expedientes prepagados usando el mismo wizard pero con contexto diferente
                await this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Crear Nuevo Expediente Prepagado',
                    res_model: 'expedient.create.wizard',  // Mismo wizard pero con contexto prepagado
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {...this.props.context, 'default_expedient_type': 'pre_paid', 'prepaid_mode': true},
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
            return true;
        }

        // También verificamos las otras flags por compatibilidad
        if (context.default_is_expedient ||
            context.search_default_is_expedient ||
            (context.default_expedient_type && context.default_expedient_type === 'post_paid') ||
            context.search_default_expedient_filter) {
            return true;
        }

        return false;
    },

    _isPrepaidView() {
        const context = this.props.context || {};

        // Verificar si estamos en la vista de expedientes prepagados
        if (this.props.resModel === 'pre.paid.expedient') {
            return true;
        }

        // Verificar por contexto
        if (context.default_expedient_type && context.default_expedient_type === 'pre_paid') {
            return true;
        }

        return false;
    }
});
