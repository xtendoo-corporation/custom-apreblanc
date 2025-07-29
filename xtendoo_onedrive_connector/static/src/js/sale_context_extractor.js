/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Servicio para capturar el contexto real de venta desde el navegador
 */
class SaleContextService {

    start() {
        this.setupURLMonitoring();
        return this;
    }

    setupURLMonitoring() {
        // Monitorear cambios en la URL constantemente
        let lastURL = window.location.href;
        let lastHash = window.location.hash;

        // Actualizar inmediatamente al cargar
        this.updateCurrentSaleContext();

        // Monitorear cada 500ms para capturar cambios rápidos
        setInterval(() => {
            const currentURL = window.location.href;
            const currentHash = window.location.hash;

            if (currentURL !== lastURL || currentHash !== lastHash) {
                lastURL = currentURL;
                lastHash = currentHash;
                this.updateCurrentSaleContext();
            }
        }, 500);

        // También escuchar eventos de navegación
        window.addEventListener('popstate', () => {
            setTimeout(() => this.updateCurrentSaleContext(), 100);
        });

        // Escuchar cambios en el DOM que indiquen navegación
        const observer = new MutationObserver(() => {
            this.updateCurrentSaleContext();
        });

        // Observar cambios en elementos que contienen información de la vista actual
        const targetNode = document.querySelector('body');
        if (targetNode) {
            observer.observe(targetNode, {
                attributes: true,
                attributeFilter: ['data-view-id', 'data-model', 'data-res-id'],
                subtree: true
            });
        }
    }

    updateCurrentSaleContext() {
        const saleId = this.extractCurrentSaleId();
        if (saleId) {
            this.storeSaleContext(saleId);
            console.log(`🎯 SaleContext actualizado: ID ${saleId}`);
        }
    }

    extractCurrentSaleId() {
        try {
            const url = window.location.href;
            const hash = window.location.hash;

            console.log('🔍 Extracting from URL:', url);
            console.log('🔍 Extracting from Hash:', hash);

            // Patrones para detectar sale.order
            const patterns = [
                // Patrones específicos para sale.order
                /[#&?]id=(\d+).*model=sale\.order/,
                /[#&?]model=sale\.order.*id=(\d+)/,
                /[#&?]res_model=sale\.order.*res_id=(\d+)/,
                /[#&?]res_id=(\d+).*res_model=sale\.order/,
                // Patrones en el hash
                /#.*action=\d+.*id=(\d+)/,
                /#.*id=(\d+).*action=\d+/,
                // Patrón más general pero con validación
                /[#&?]id=(\d+)/
            ];

            // Buscar en URL completa primero
            for (const pattern of patterns) {
                const match = url.match(pattern);
                if (match) {
                    const id = parseInt(match[1]);
                    console.log(`✅ ID ${id} encontrado en URL con patrón:`, pattern.source);

                    // Validar que realmente estamos en una vista de sale.order
                    if (this.validateSaleOrderContext(url, hash)) {
                        return id;
                    }
                }
            }

            // Si no encontramos en URL, buscar en elementos del DOM
            const domId = this.extractFromDOM();
            if (domId) {
                console.log(`✅ ID ${domId} encontrado en DOM`);
                return domId;
            }

            console.log('❌ No se encontró ID de sale.order');
            return null;

        } catch (error) {
            console.error('❌ Error extrayendo sale ID:', error);
            return null;
        }
    }

    validateSaleOrderContext(url, hash) {
        // Verificar que estamos realmente en un contexto de sale.order
        const indicators = [
            'model=sale.order',
            'res_model=sale.order',
            '/sale/',
            'sale.order'
        ];

        const fullContext = url + hash;
        return indicators.some(indicator => fullContext.includes(indicator));
    }

    extractFromDOM() {
        try {
            // Buscar en atributos del DOM que contengan información del registro actual
            const selectors = [
                '[data-res-id]',
                '[data-record-id]',
                '.o_form_view[data-res-id]',
                '.o_list_view .o_data_row.o_selected',
                '.breadcrumb .active'
            ];

            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    const resId = el.getAttribute('data-res-id') ||
                                 el.getAttribute('data-record-id') ||
                                 el.getAttribute('data-id');

                    if (resId && !isNaN(resId)) {
                        // Verificar que el contexto del elemento sea sale.order
                        const model = el.getAttribute('data-model') ||
                                     el.getAttribute('data-res-model') ||
                                     document.querySelector('[data-model="sale.order"]');

                        if (model && (model === 'sale.order' || model.includes('sale.order'))) {
                            return parseInt(resId);
                        }
                    }
                }
            }

            // Buscar en la barra de título o breadcrumb
            const titleElements = document.querySelectorAll('.breadcrumb .active, .o_form_view .o_control_panel h1');
            for (const titleEl of titleElements) {
                const text = titleEl.textContent || '';
                const match = text.match(/S\d{5}/); // Patrón típico de sale orders
                if (match) {
                    // Esto es solo el nombre, necesitaríamos hacer una búsqueda inversa
                    console.log('🔍 Nombre de venta encontrado en DOM:', match[0]);
                }
            }

            return null;
        } catch (error) {
            console.error('❌ Error extrayendo del DOM:', error);
            return null;
        }
    }

    storeSaleContext(saleId) {
        try {
            const context = {
                saleId: saleId,
                timestamp: Date.now(),
                url: window.location.href,
                hash: window.location.hash,
                userAgent: navigator.userAgent.substring(0, 100) // Identificador de sesión
            };

            // Almacenar en múltiples lugares para redundancia
            sessionStorage.setItem('odoo_current_sale_id', saleId.toString());
            sessionStorage.setItem('odoo_sale_context', JSON.stringify(context));
            localStorage.setItem('odoo_last_sale_id', saleId.toString());

            // También en una variable global para acceso inmediato
            window.ODOO_CURRENT_SALE_ID = saleId;

            // NUEVO: Almacenar en cookie para que Python pueda leerlo
            document.cookie = `odoo_current_sale_id=${saleId}; path=/; max-age=3600; SameSite=Lax`;

            // También enviar como header personalizado en próximas requests
            if (window.XMLHttpRequest) {
                const originalOpen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
                    const result = originalOpen.apply(this, arguments);
                    this.setRequestHeader('X-Odoo-Sale-ID', saleId.toString());
                    return result;
                };
            }

            console.log('💾 Contexto almacenado con cookie:', context);

        } catch (error) {
            console.error('❌ Error almacenando contexto:', error);
        }
    }

    getCurrentSaleId() {
        try {
            // Prioridad 1: Variable global (más fresco)
            if (window.ODOO_CURRENT_SALE_ID) {
                console.log('📂 ID desde variable global:', window.ODOO_CURRENT_SALE_ID);
                return window.ODOO_CURRENT_SALE_ID;
            }

            // Prioridad 2: SessionStorage
            const sessionId = sessionStorage.getItem('odoo_current_sale_id');
            if (sessionId) {
                const id = parseInt(sessionId);
                console.log('📂 ID desde sessionStorage:', id);
                return id;
            }

            // Prioridad 3: Extraer en tiempo real
            const liveId = this.extractCurrentSaleId();
            if (liveId) {
                console.log('📂 ID extraído en tiempo real:', liveId);
                return liveId;
            }

            console.log('❌ No se pudo obtener sale ID');
            return null;

        } catch (error) {
            console.error('❌ Error obteniendo sale ID:', error);
            return null;
        }
    }

    // Método para que Python pueda acceder al ID actual
    getSaleIdForPython() {
        const id = this.getCurrentSaleId();
        if (id) {
            // Actualizar también el contexto almacenado
            this.storeSaleContext(id);
            return {
                success: true,
                saleId: id,
                timestamp: Date.now()
            };
        }

        return {
            success: false,
            error: 'No sale ID found'
        };
    }
}

// Registrar el servicio
registry.category("services").add("saleContext", {
    start(env, services) {
        const service = new SaleContextService();
        return service.start();
    },
});

// Hacer disponible globalmente para que Python pueda acceder
window.getSaleContext = () => {
    const service = odoo.__DEBUG__.services.saleContext;
    if (service) {
        return service.getSaleIdForPython();
    }
    return { success: false, error: 'Service not available' };
};

// Inicialización inmediata
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 SaleContext service initializing...');
});

// También ejecutar inmediatamente si el DOM ya está listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

function initialize() {
    // Configurar captura inmediata
    const service = new SaleContextService();
    service.start();

    // Hacer disponible globalmente
    window.SALE_CONTEXT_SERVICE = service;
}
