odoo.define('sale_order_expedient.ExpedientListController', function (require) {
    "use strict";

    // Importar los módulos base necesarios
    const ListController = require('web.ListController');
    const ListView = require('web.ListView');
    const viewRegistry = require('web.view_registry');

    // No necesitamos un controlador personalizado ya que usamos el botón en el header
    // que simplemente llama a una acción definida en XML

    // Registrar la vista de lista normal para los expedientes
    viewRegistry.add('expedient_list', ListView);

    return ListView;
});
