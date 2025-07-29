/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

/**
 * Extractor de contexto de venta para evitar problemas de cache
 */
export class SaleContextExtractor {

    /**
     * Extraer ID de venta desde la URL actual del navegador
     */
    static extractSaleIdFromCurrentURL() {
        try {
            const currentURL = window.location.href;
            const currentHash = window.location.hash;

            console.log('🔍 SaleContextExtractor - URL actual:', currentURL);
            console.log('🔍 SaleContextExtractor - Hash actual:', currentHash);

            // Patrones para buscar ID de sale.order en la URL
            const patterns = [
                /id=(\d+).*model=sale\.order/,
                /model=sale\.order.*id=(\d+)/,
                /\/web#.*id=(\d+).*model=sale\.order/,
                /\/web#.*model=sale\.order.*id=(\d+)/,
                /action=\d+.*id=(\d+)/,
                /res_id=(\d+).*res_model=sale\.order/,
                /res_model=sale\.order.*res_id=(\d+)/,
            ];

            // Buscar en URL completa
            for (const pattern of patterns) {
                const match = currentURL.match(pattern);
                if (match) {
                    const saleId = parseInt(match[1]);
                    console.log('✅ SaleContextExtractor - ID encontrado en URL:', saleId);
                    return saleId;
                }
            }

            // Buscar específicamente en el hash
            if (currentHash) {
                for (const pattern of patterns) {
                    const match = currentHash.match(pattern);
                    if (match) {
                        const saleId = parseInt(match[1]);
                        console.log('✅ SaleContextExtractor - ID encontrado en hash:', saleId);
                        return saleId;
                    }
                }
            }

            console.log('❌ SaleContextExtractor - No se encontró ID en URL');
            return null;

        } catch (error) {
            console.error('❌ SaleContextExtractor - Error:', error);
            return null;
        }
    }

    /**
     * Extraer ID desde el estado de Odoo web client
     */
    static extractSaleIdFromOdooState() {
        try {
            // Intentar obtener desde el estado actual de Odoo
            if (window.odoo && window.odoo.__DEBUG__) {
                const debug = window.odoo.__DEBUG__;
                if (debug.services && debug.services.action) {
                    const actionService = debug.services.action;
                    const currentAction = actionService.currentController;

                    if (currentAction && currentAction.props) {
                        const props = currentAction.props;
                        if (props.resModel === 'sale.order' && props.resId) {
                            console.log('✅ SaleContextExtractor - ID desde Odoo state:', props.resId);
                            return props.resId;
                        }
                    }
                }
            }

            // Intentar desde variables globales de Odoo
            if (window.odoo && window.odoo.action_registry) {
                // Buscar en registry
                console.log('🔍 SaleContextExtractor - Buscando en registry...');
            }

            return null;

        } catch (error) {
            console.error('❌ SaleContextExtractor - Error en Odoo state:', error);
            return null;
        }
    }

    /**
     * Método principal para obtener el ID de venta actual
     */
    static getCurrentSaleId() {
        // Prioridad 1: URL actual
        let saleId = this.extractSaleIdFromCurrentURL();
        if (saleId) return saleId;

        // Prioridad 2: Estado de Odoo
        saleId = this.extractSaleIdFromOdooState();
        if (saleId) return saleId;

        console.log('❌ SaleContextExtractor - No se pudo obtener ID de venta');
        return null;
    }

    /**
     * Almacenar ID en sessionStorage para persistencia
     */
    static storeSaleId(saleId) {
        try {
            const timestamp = Date.now();
            const data = {
                saleId: saleId,
                timestamp: timestamp,
                url: window.location.href
            };
            sessionStorage.setItem('current_sale_context', JSON.stringify(data));
            console.log('💾 SaleContextExtractor - ID almacenado:', data);
        } catch (error) {
            console.error('❌ SaleContextExtractor - Error almacenando:', error);
        }
    }

    /**
     * Recuperar ID desde sessionStorage
     */
    static getStoredSaleId() {
        try {
            const stored = sessionStorage.getItem('current_sale_context');
            if (stored) {
                const data = JSON.parse(stored);
                const ageMinutes = (Date.now() - data.timestamp) / (1000 * 60);

                // Solo usar si es menor a 5 minutos
                if (ageMinutes < 5) {
                    console.log('📂 SaleContextExtractor - ID recuperado del storage:', data.saleId);
                    return data.saleId;
                }
            }
            return null;
        } catch (error) {
            console.error('❌ SaleContextExtractor - Error recuperando:', error);
            return null;
        }
    }
}

// Registrar el servicio
registry.category("services").add("saleContextExtractor", {
    start() {
        return SaleContextExtractor;
    },
});

// Monitorear cambios de URL para actualizar contexto
let lastURL = window.location.href;
setInterval(() => {
    const currentURL = window.location.href;
    if (currentURL !== lastURL) {
        lastURL = currentURL;
        const saleId = SaleContextExtractor.getCurrentSaleId();
        if (saleId) {
            SaleContextExtractor.storeSaleId(saleId);
        }
    }
}, 1000);

// También al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    const saleId = SaleContextExtractor.getCurrentSaleId();
    if (saleId) {
        SaleContextExtractor.storeSaleId(saleId);
    }
});
