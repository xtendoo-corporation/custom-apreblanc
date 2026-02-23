===========================
Apreblanc Credit Control
===========================

.. |badge_version| image:: https://img.shields.io/badge/version-17.0.1.0.0-blue
.. |badge_license| image:: https://img.shields.io/badge/license-AGPL--3-green

|badge_version| |badge_license|

Módulo de control de crédito simplificado para Apreblanc. Permite identificar
clientes con deuda vencida superior a un límite configurable, visualizar el
importe vencido y el importe pendiente de vencer, y enviar recordatorios por
email con el detalle de facturas. Deja registro del historial de comunicaciones
en la ficha de cada cliente.

**Características principales:**

- Análisis **bajo demanda**: se lanza cuando el responsable lo decide.
- **Límite de deuda vencida** configurable por empresa.
- Soporte **multimoneda**: convierte a la moneda de la empresa usando el tipo de
  cambio de la fecha del análisis.
- **Completamente independiente**: solo depende del módulo ``account``.
- Email de recordatorio con **dos secciones** diferenciadas: facturas vencidas
  (en rojo) y facturas pendientes de vencer (en amarillo), cada una con su
  total al pie.
- **Historial de recordatorios** en la ficha del cliente: fecha, importes
  comunicados y usuario responsable.

.. contents:: Tabla de contenidos
   :local:

Instalación
===========

El módulo se instala desde la interfaz de Odoo o mediante línea de comandos::

    odoo -d <base_de_datos> -i apreblanc_credit_control --stop-after-init

Configuración
=============

1. Ve a **Contabilidad → Configuración → Ajustes**.
2. En la sección **Control de Crédito Apreblanc** introduce el **Límite de
   deuda vencida**: importe mínimo (en moneda de la empresa) que debe tener un
   cliente en deuda vencida para que aparezca en el análisis.
3. Guarda los ajustes.

.. note::
   El límite también puede ajustarse en cada análisis individual antes de
   calcular, sin modificar el valor global de la empresa.

Uso
===

Lanzar un análisis de deuda
---------------------------

1. Ve a **Contabilidad → Control de Crédito → Análisis de deuda**.
2. Pulsa **Nuevo**.
3. Revisa la **Fecha del análisis** (por defecto hoy) y el **Límite de deuda
   vencida** (se carga desde la configuración de la empresa).
4. Pulsa **Calcular deuda**.

El sistema procesará todos los apuntes contables de cobro no conciliados de
facturas de cliente confirmadas y:

- Agrupará por cliente comercial.
- Convertirá los importes a la moneda de la empresa (tipo de cambio de la fecha
  del análisis).
- Separará los importes en **vencidos** (fecha de vencimiento < fecha análisis)
  y **pendientes de vencer** (aún no vencidos pero sin pagar).
- Incluirá solo los clientes cuya deuda vencida supere el límite.

La pestaña **Clientes con deuda** mostrará el resultado con los siguientes
campos por cliente:

+--------------------------------+----------------------------------------------+
| Campo                          | Descripción                                  |
+================================+==============================================+
| Cliente                        | Nombre del cliente comercial                 |
+--------------------------------+----------------------------------------------+
| Importe vencido                | Total de facturas con vencimiento superado   |
+--------------------------------+----------------------------------------------+
| Importe pendiente de vencer    | Total de facturas aún no vencidas sin pagar  |
+--------------------------------+----------------------------------------------+
| Total deuda                    | Suma de ambos importes                       |
+--------------------------------+----------------------------------------------+
| Email enviado                  | Indica si ya se envió recordatorio           |
+--------------------------------+----------------------------------------------+

Enviar un recordatorio por email
---------------------------------

1. Desde la lista de clientes del análisis, pulsa el botón ✉ **Enviar email**
   de la fila del cliente deseado.
2. Se abrirá el **compositor de correo** de Odoo con el template precargado.
3. El email incluye automáticamente:

   - **Tabla de facturas vencidas** (encabezado rojo): nº factura, fecha
     factura, fecha de vencimiento y importe pendiente. Total al pie.
   - **Tabla de facturas pendientes de vencer** (encabezado amarillo): mismos
     campos. Total al pie.

4. Revisa el destinatario y el contenido, personaliza si es necesario y pulsa
   **Enviar**.
5. El sistema registra automáticamente el envío como un **recordatorio** en la
   ficha del cliente.

.. important::
   El botón **Enviar email** también está disponible abriendo la línea del
   cliente en detalle (vista formulario), donde además puedes consultar el
   desglose completo de facturas en las pestañas **Facturas vencidas** y
   **Facturas pendientes de vencer**.

Consultar el historial de recordatorios
----------------------------------------

Desde la **ficha del cliente** (Contabilidad → Clientes o Ventas → Clientes):

- Pestaña **Recordatorios de crédito**: lista completa de todos los
  recordatorios enviados.
- Botón estadístico 🔔 en la cabecera: acceso directo al historial (visible
  cuando hay al menos un recordatorio).

Cada registro del historial contiene:

+--------------------------------+----------------------------------------------+
| Campo                          | Descripción                                  |
+================================+==============================================+
| Fecha de envío                 | Día en que se envió el recordatorio          |
+--------------------------------+----------------------------------------------+
| Importe vencido comunicado     | Deuda vencida informada en ese envío         |
+--------------------------------+----------------------------------------------+
| Importe pendiente comunicado   | Deuda pendiente informada en ese envío       |
+--------------------------------+----------------------------------------------+
| Enviado por                    | Usuario responsable del envío                |
+--------------------------------+----------------------------------------------+
| Análisis                       | Referencia al análisis del que proviene      |
+--------------------------------+----------------------------------------------+
| Notas                          | Campo libre para anotaciones internas        |
+--------------------------------+----------------------------------------------+

Recalcular un análisis
-----------------------

Si necesitas actualizar los datos de un análisis ya calculado:

1. Abre el análisis.
2. Pulsa **Recalcular**.
3. Confirma la acción en el diálogo de confirmación.

.. warning::
   Al recalcular se **eliminan todas las líneas** del análisis y se generan de
   nuevo. Los recordatorios de email ya enviados **no se eliminan** y quedan
   preservados en la ficha del cliente.

Permisos y grupos de seguridad
===============================

El módulo define dos grupos dentro de la categoría **Control de Crédito
Apreblanc**:

+-------------------+------------------------------------------------------------+
| Grupo             | Acceso                                                     |
+===================+============================================================+
| **Usuario**       | Solo lectura: ver análisis, líneas e historial de          |
|                   | recordatorios en la ficha del cliente.                     |
+-------------------+------------------------------------------------------------+
| **Responsable**   | Lectura y escritura completa: crear y lanzar análisis,     |
|                   | enviar emails, configurar el límite en Ajustes.            |
+-------------------+------------------------------------------------------------+

Estructura técnica
==================

Modelos creados
---------------

+--------------------------------+----------------------------------------------+
| Modelo                         | Descripción                                  |
+================================+==============================================+
| ``apreblanc.credit.run``       | Análisis de deuda (cabecera)                 |
+--------------------------------+----------------------------------------------+
| ``apreblanc.credit.line``      | Línea por cliente dentro de un análisis      |
+--------------------------------+----------------------------------------------+
| ``apreblanc.credit.invoice``   | Detalle de factura individual                |
+--------------------------------+----------------------------------------------+
| ``apreblanc.credit.reminder``  | Registro histórico de recordatorio enviado   |
+--------------------------------+----------------------------------------------+

Campos extendidos
-----------------

- ``res.company``: campo ``credit_control_debt_limit`` (límite global).
- ``res.config.settings``: campo relacionado para editar el límite en Ajustes.
- ``res.partner``: ``credit_reminder_ids`` (One2many al historial) y
  ``credit_reminder_count`` (contador para el botón stat).

Créditos
========

Autores
-------

* `Xtendoo <http://www.xtendoo.es>`_

Licencia
--------

Este módulo se distribuye bajo licencia `AGPL-3
<http://www.gnu.org/licenses/agpl-3.0-standalone.html>`_.

