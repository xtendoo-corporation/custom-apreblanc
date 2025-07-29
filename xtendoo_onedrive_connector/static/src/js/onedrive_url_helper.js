/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Helper mejorado para obtener el ID de sale.order desde la URL actual del navegador
 * Solución directa al problema del contexto cacheado en Odoo
 */
export class OneDriveUrlHelper {

    /**
     * Obtener el sale_order_id desde la URL actual del navegador
     * @returns {number|null} ID de la venta o null si no se encuentra
     */
    static getCurrentSaleOrderId() {
        try {
            // Obtener TODAS las URLs posibles
            const currentUrl = window.location.href;
            const hash = window.location.hash;
            const search = window.location.search;

            console.log("🔍 OneDrive URL Helper - URL completa:", currentUrl);
            console.log("🔍 OneDrive URL Helper - Hash:", hash);
            console.log("🔍 OneDrive URL Helper - Search:", search);

            // Lista de todas las URLs a analizar
            const urlsToCheck = [
                currentUrl,
                hash,
                search,
                decodeURIComponent(currentUrl),
                decodeURIComponent(hash),
                decodeURIComponent(search)
            ];

            // Patrones MÁS AGRESIVOS para encontrar el ID
            const patterns = [
                // Patrones específicos para sale.order
                /[#&?]id=(\d+)[^&]*model=sale\.order/i,
                /[#&?]model=sale\.order[^&]*id=(\d+)/i,

                // Patrones con action
                /action=\d+[^&]*id=(\d+)[^&]*model=sale\.order/i,
                /action=\d+[^&]*model=sale\.order[^&]*id=(\d+)/i,

                // Patrones más generales para cualquier id cuando hay sale.order
                /sale\.order.*?id[=,](\d+)/i,
                /id[=,](\d+).*?sale\.order/i,

                // Patrones para URLs codificadas
                /%2Cid%2C(\d+).*?sale\.order/i,
                /sale\.order.*?%2Cid%2C(\d+)/i,

                // Patrones para estructuras de Odoo específicas
                /\/web#.*id,(\d+).*model,sale\.order/i,
                /\/web#.*model,sale\.order.*id,(\d+)/i,

                // Patrón simple para cualquier id= seguido de números cuando está presente sale.order
                /id=(\d+)(?=.*sale\.order|.*venta|.*pedido)/i,

                // Último recurso: cualquier id= en URLs que contengan sale
                /id=(\d+)(?=.*sale)/i,
            ];

            // Buscar en todas las URLs con todos los patrones
            for (const url of urlsToCheck) {
                if (!url) continue;

                console.log(`🔍 Analizando URL: ${url}`);

                for (const pattern of patterns) {
                    const match = url.match(pattern);
                    if (match && match[1]) {
                        const saleId = parseInt(match[1]);
                        console.log(`✅ Sale ID encontrado: ${saleId} con patrón: ${pattern}`);

                        // Validar que es un número válido
                        if (!isNaN(saleId) && saleId > 0) {
                            return saleId;
                        }
                    }
                }
            }

            // Si no encontramos nada específico, buscar el patrón más simple
            // en la URL cuando contiene la palabra "sale"
            for (const url of urlsToCheck) {
                if (!url || !url.toLowerCase().includes('sale')) continue;

                const simpleMatch = url.match(/id=(\d+)/i);
                if (simpleMatch && simpleMatch[1]) {
                    const saleId = parseInt(simpleMatch[1]);
                    console.log(`⚠️ Sale ID encontrado (patrón simple): ${saleId}`);
                    return saleId;
                }
            }

            console.log("❌ No se encontró Sale ID en ninguna URL");
            return null;

        } catch (error) {
            console.error("❌ OneDrive URL Helper - Error:", error);
            return null;
        }
    }

    /**
     * Método mejorado que también verifica en el DOM si hay información adicional
     */
    static getCurrentSaleOrderIdWithDOMCheck() {
        // Primero intentar desde URL
        let saleId = this.getCurrentSaleOrderId();

        if (saleId) {
            return saleId;
        }

        // Si no encontramos en URL, buscar en el DOM
        try {
            // Buscar en el título de la página
            const pageTitle = document.title;
            console.log("🔍 Título de página:", pageTitle);

            const titleMatch = pageTitle.match(/S\d+/); // Patrón típico de ventas como S00123
            if (titleMatch) {
                console.log(`📄 Patrón de venta encontrado en título: ${titleMatch[0]}`);
            }

            // Buscar en elementos que puedan contener el ID
            const breadcrumbs = document.querySelector('.o_breadcrumb');
            if (breadcrumbs) {
                const breadcrumbText = breadcrumbs.textContent;
                console.log("🍞 Breadcrumb:", breadcrumbText);

                const breadcrumbMatch = breadcrumbText.match(/S\d+/);
                if (breadcrumbMatch) {
                    console.log(`🍞 Patrón de venta en breadcrumb: ${breadcrumbMatch[0]}`);
                }
            }

        } catch (error) {
            console.error("Error verificando DOM:", error);
        }

        return null;
    }

    /**
     * Método para monitorear cambios en la URL y actualizar el ID de la venta
     */
    static monitorUrlChanges(callback) {
        let lastUrl = window.location.href;

        setInterval(() => {
            const currentUrl = window.location.href;
            if (currentUrl !== lastUrl) {
                lastUrl = currentUrl;
                console.log("🔄 URL cambiada, verificando nuevo Sale ID");
                const saleId = this.getCurrentSaleOrderId();
                if (saleId) {
                    console.log(`🔄 Nuevo Sale ID detectado: ${saleId}`);
                    callback(saleId);
                }
            }
        }, 1000); // Verificar cada segundo
    }
}

// Registrar el helper globalmente
window.OneDriveUrlHelper = OneDriveUrlHelper;

// Registrar en el registry de Odoo
registry.category("services").add("onedrive_url_helper", {
    start() {
        return OneDriveUrlHelper;
    },
});
