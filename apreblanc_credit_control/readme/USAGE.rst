Configuración inicial
~~~~~~~~~~~~~~~~~~~~~

#. Ve a **Contabilidad → Configuración → Ajustes**.
#. En la sección **Control de Crédito Apreblanc** introduce el importe mínimo
   de deuda vencida a partir del cual un cliente aparecerá en el análisis.
#. Guarda los ajustes.

Lanzar un análisis de deuda
~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Ve a **Contabilidad → Control de Crédito → Análisis de deuda**.
#. Pulsa **Nuevo** para crear un nuevo análisis.
#. Ajusta la **Fecha del análisis** (por defecto hoy) y el **Límite de deuda
   vencida** si quieres usar un valor diferente al de la configuración.
#. Pulsa **Calcular deuda**.

   El sistema recorre todos los apuntes contables de cobro pendientes de
   conciliar en facturas de cliente confirmadas y:

   - Convierte los importes a la moneda de la empresa usando el tipo de cambio
     de la fecha del análisis.
   - Agrupa por cliente comercial.
   - Calcula el **importe vencido** (vencimiento anterior a la fecha del
     análisis) y el **importe pendiente de vencer** (aún no vencido pero sin
     pagar).
   - Solo incluye clientes cuya deuda vencida supera el límite configurado.

#. La pestaña **Clientes con deuda** mostrará una línea por cada cliente
   afectado con sus totales.

Enviar un recordatorio por email
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Desde la lista de clientes del análisis, pulsa el botón **Enviar email** de
   la fila del cliente (o abre la línea y usa el botón del encabezado).
#. Se abrirá el compositor de correo de Odoo con el **template de recordatorio
   precargado**, que incluye:

   - Una tabla de **facturas vencidas** (fondo rojo) con el total al pie.
   - Una tabla de **facturas pendientes de vencer** (fondo amarillo) con el
     total al pie.

#. Revisa el destinatario, personaliza el mensaje si es necesario y pulsa
   **Enviar**.
#. Al enviar, el sistema crea automáticamente un **registro de recordatorio**
   en la ficha del cliente.

Consultar el historial de recordatorios de un cliente
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Abre la ficha de un cliente desde **Contabilidad → Clientes** o desde
   **Ventas → Clientes**.
#. Ve a la pestaña **Recordatorios de crédito**.
#. Verás la lista completa de recordatorios enviados con: fecha de envío,
   importe vencido comunicado, importe pendiente comunicado, usuario responsable
   y referencia al análisis.
#. También puedes pulsar el botón estadístico 🔔 de la cabecera para acceder
   directamente al historial.

Recalcular un análisis existente
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Abre el análisis y pulsa **Recalcular**.
#. El sistema eliminará todas las líneas y las generará de nuevo con los datos
   actualizados. Los recordatorios ya enviados **no** se eliminan.

