/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Cliente para manejar la subida de archivos a OneDrive con detección automática
 * del ID de venta desde la URL cuando el contexto está desactualizado
 */
export class OneDriveUploadClient {
    constructor(env, action) {
        this.env = env;
        this.action = action;
        this.rpc = useService("rpc");
        this.notification = useService("notification");
    }

    async start() {
        try {
            console.log("🚀 OneDrive Upload Client - Iniciando detección desde URL");

            // Obtener el ID del record desde los parámetros
            const recordId = this.action.params.record_id;
            if (!recordId) {
                throw new Error("No se proporcionó record_id");
            }

            // Usar el helper para obtener el sale ID desde la URL
            const saleId = window.OneDriveUrlHelper?.getCurrentSaleOrderId();

            if (!saleId) {
                this.notification.add("No se pudo obtener el ID de la venta desde la URL. Por favor, recarga la página (F5) y vuelve a intentar.", {
                    title: "Error - URL no válida",
                    type: "warning",
                    sticky: true
                });
                return;
            }

            console.log(`✅ OneDrive Upload Client - Sale ID obtenido: ${saleId}`);

            // Mostrar notificación de progreso
            this.notification.add("Procesando subida a OneDrive...", {
                title: "Subiendo archivo",
                type: "info",
                sticky: false
            });

            // Llamar al método específico que maneja el sale_id desde JavaScript
            console.log("🔄 OneDrive Upload Client - Ejecutando upload con sale_id");

            const result = await this.rpc("/web/dataset/call_kw", {
                model: "onedrive.document",
                method: "action_upload_file_with_sale_id",
                args: [recordId, saleId],
                kwargs: {}
            });

            console.log("📤 OneDrive Upload Client - Resultado:", result);

            // Manejar la respuesta
            if (result && result.params) {
                const params = result.params;
                let notificationType = "success";

                // Mapear tipos de notificación
                if (params.type === "danger") notificationType = "danger";
                else if (params.type === "warning") notificationType = "warning";

                this.notification.add(params.message || "Operación completada", {
                    title: params.title || "Resultado",
                    type: notificationType,
                    sticky: params.sticky || false
                });

                // Si fue exitoso, cerrar cualquier modal abierto
                if (notificationType === "success") {
                    this.env.services.action.doAction({
                        type: 'ir.actions.act_window_close'
                    });
                }
            } else {
                this.notification.add("Archivo subido exitosamente", {
                    title: "Éxito",
                    type: "success",
                    sticky: false
                });

                // Cerrar modal
                this.env.services.action.doAction({
                    type: 'ir.actions.act_window_close'
                });
            }

        } catch (error) {
            console.error("❌ OneDrive Upload Client - Error:", error);

            this.notification.add(`Error durante la subida: ${error.message || error}`, {
                title: "Error",
                type: "danger",
                sticky: true
            });
        }
    }
}

// Registrar el cliente para la acción personalizada
registry.category("actions").add("onedrive_upload_with_url_detection", OneDriveUploadClient);
