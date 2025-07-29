/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

/**
 * Helper para obtener el ID de sale.order desde la URL actual del navegador
 * Esto resuelve el problema del contexto cacheado en Odoo
 */
export class OneDriveUrlHelper {

    /**
     * Obtener el sale_order_id desde la URL actual del navegador
     * @returns {number|null} ID de la venta o null si no se encuentra
     */
    static getCurrentSaleOrderId() {
        try {
            // Obtener la URL actual completa
            const currentUrl = window.location.href;
            const hash = window.location.hash;

            console.log("🔍 OneDrive URL Helper - URL actual:", currentUrl);
            console.log("🔍 OneDrive URL Helper - Hash:", hash);

            // Patrones para buscar el ID de sale.order en diferentes formatos de URL de Odoo
            const patterns = [
                // URLs con parámetros en el hash (#)
                /[#&?]id=(\d+)[^&]*(?:&[^&]*)*model=sale\.order/,
                /[#&?]model=sale\.order[^&]*(?:&[^&]*)*id=(\d+)/,

                // URLs con parámetros normales
                /[?&]id=(\d+)[^&]*(?:&[^&]*)*model=sale\.order/,
                /[?&]model=sale\.order[^&]*(?:&[^&]*)*id=(\d+)/,

                // Patrones con action
                /action=\d+[^&]*id=(\d+)[^&]*model=sale\.order/,
                /action=\d+[^&]*model=sale\.order[^&]*id=(\d+)/,

                // URLs de Odoo con estructura específica
                /\/web#.*id,(\d+).*model,sale\.order/,
                /\/web#.*model,sale\.order.*id,(\d+)/
            ];

            // Buscar en la URL completa
            for (const pattern of patterns) {
                const match = currentUrl.match(pattern);
                if (match && match[1]) {
                    const saleId = parseInt(match[1]);
                    console.log("✅ OneDrive URL Helper - Sale ID encontrado:", saleId, "con patrón:", pattern);
                    return saleId;
                }
            }

            // Si no encontramos nada, intentar buscar solo números que podrían ser IDs
            // después de palabras clave relacionadas con sale order
            const fallbackPatterns = [
                /sale.*order.*(\d+)/i,
                /venta.*(\d+)/i,
                /pedido.*(\d+)/i
            ];

            for (const pattern of fallbackPatterns) {
                const match = currentUrl.match(pattern);
                if (match && match[1]) {
                    const saleId = parseInt(match[1]);
                    console.log("⚠️ OneDrive URL Helper - Sale ID encontrado (fallback):", saleId);
                    return saleId;
                }
            }

            console.log("❌ OneDrive URL Helper - No se encontró Sale ID en la URL");
            return null;

        } catch (error) {
            console.error("❌ OneDrive URL Helper - Error:", error);
            return null;
        }
    }

    /**
     * Enviar el sale_order_id actual al servidor para que lo use OneDrive
     * @param {Object} rpc - Servicio RPC de Odoo
     * @returns {Promise<string|null>} Nombre de la venta o null
     */
    static async getSaleOrderName(rpc) {
        try {
            const saleId = this.getCurrentSaleOrderId();

            if (!saleId) {
                console.log("❌ OneDrive URL Helper - No hay Sale ID para obtener nombre");
                return null;
            }

            console.log("🔄 OneDrive URL Helper - Obteniendo nombre para Sale ID:", saleId);

            // Llamar al servidor para obtener el nombre de la venta
            const result = await rpc('/web/dataset/call_kw', {
                model: 'sale.order',
                method: 'read',
                args: [[saleId], ['name']],
                kwargs: {}
            });

            if (result && result.length > 0 && result[0].name) {
                const saleName = result[0].name;
                console.log("✅ OneDrive URL Helper - Nombre obtenido:", saleName);
                return saleName;
            }

            console.log("❌ OneDrive URL Helper - No se pudo obtener el nombre");
            return null;

        } catch (error) {
            console.error("❌ OneDrive URL Helper - Error obteniendo nombre:", error);
            return null;
        }
    }
}

// Registrar el helper globalmente para que sea accesible
window.OneDriveUrlHelper = OneDriveUrlHelper;

// También registrarlo en el registry de Odoo para uso en componentes
registry.category("services").add("onedrive_url_helper", {
    start() {
        return OneDriveUrlHelper;
    },
});
