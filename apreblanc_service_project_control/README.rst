Apreblanc Service Project Control
=================================

Resumen funcional
-----------------

Este módulo añade un control operativo para servicios vendidos desde pedidos de
venta estándar en Odoo.

Cuando se confirma un pedido con líneas de servicio:

* se crea un proyecto operativo asociado al pedido,
* se genera una tarea por cada línea de servicio,
* se calcula una bolsa de horas objetivo en función del producto y la cantidad,
* se monitoriza el consumo horario real mediante partes de horas,
* se bloquean nuevas imputaciones cuando se supera el objetivo, salvo
  autorización expresa.

Objetivo del módulo
-------------------

El objetivo es controlar la rentabilidad operativa de auditorías, formaciones y
servicios similares sin alterar el flujo estándar de venta ni supeditar la
facturación a las horas imputadas.

Configuración previa
--------------------

Antes de usar el módulo conviene revisar estos puntos:

* El producto debe ser de tipo servicio.
* En la ficha del producto debe informarse el campo ``Horas objetivo servicio``.
* El usuario que vaya a imputar horas debe poder usar partes de horas en
  proyecto.
* El pedido de venta debe seguir el flujo estándar de confirmación.

Campos que añade el módulo
--------------------------

``product.template``
    Campo ``Horas objetivo servicio`` para definir las horas previstas por cada
    unidad vendida.

``sale.order.line``
    Campo calculado ``Horas objetivo`` en función de cantidad por horas objetivo
    del producto.

``sale.order``
    Enlace al ``Proyecto operativo`` y métricas agregadas de control horario.

``project.project``
    Marcador de control Apreblanc, pedido origen, responsables y métricas de
    horas, desviación y rentabilidad.

``project.task``
    Trazabilidad con la línea del pedido que originó la tarea.

``account.analytic.line``
    Validación del límite horario antes de aceptar nuevas imputaciones.

Manual de uso
-------------

1. Crear o revisar el producto de servicio.

   * Abrir el producto.
   * Indicar el valor de ``Horas objetivo servicio``.
   * Guardar el producto.

2. Crear el pedido de venta.

   * Añadir una o varias líneas de servicio.
   * La métrica de horas previstas se calculará automáticamente en cada línea.

3. Confirmar el pedido.

   * Al confirmar, el módulo crea un único proyecto operativo para el pedido.
   * También crea una tarea por cada línea de servicio.
   * En el pedido aparece el botón ``Proyecto operativo``.

4. Gestionar el proyecto.

   * Desde el proyecto se visualizan las horas presupuestadas, consumidas,
     restantes, desviación, rentabilidad y estado.
   * El proyecto conserva un enlace directo al pedido origen.
   * Puede informarse el jefe de proyecto, gestor junior y gestor senior.

5. Imputar horas.

   * Las horas se registran en tareas del proyecto mediante partes de horas.
   * Mientras no se supere el objetivo, el sistema permite seguir imputando.
   * Cuando el consumo alcanza el 80% del objetivo, el estado pasa a umbral de
     aviso.

6. Autorizar exceso horario si procede.

   * Si el proyecto supera las horas objetivo, el sistema bloquea nuevas
     imputaciones.
   * El botón ``Autorizar exceso`` habilita continuar imputando horas.
   * El botón ``Revocar autorización`` vuelve a activar el bloqueo.

Permisos y criterio de autorización
-----------------------------------

Puede autorizar o revocar el exceso horario cualquiera de estos perfiles:

* el usuario indicado como jefe de proyecto,
* un usuario del grupo de responsable de proyecto,
* un usuario administrador del sistema.

Si otro usuario intenta aprobar el exceso, Odoo mostrará un error funcional.

Indicadores operativos
----------------------

El proyecto y el pedido muestran estas métricas:

* horas presupuestadas,
* horas consumidas,
* horas restantes,
* porcentaje de consumo,
* desviación respecto al objetivo,
* rentabilidad estimada,
* estado horario.

El estado horario puede ser:

* ``Dentro de objetivo`` cuando no hay riesgo,
* ``En umbral`` cuando el consumo alcanza al menos el 80%,
* ``Excedido`` cuando se supera el objetivo sin autorización,
* ``Excedido autorizado`` cuando el exceso ha sido aprobado.

Cobertura de test añadida
-------------------------

La cobertura funcional mínima del módulo valida:

* la creación automática del proyecto al confirmar el pedido,
* la generación de tareas desde líneas de servicio,
* el cálculo de horas objetivo trasladado al proyecto,
* el bloqueo de imputaciones al superar el objetivo,
* la continuidad del registro horario tras la autorización del exceso.

Límites actuales
----------------

* El módulo crea un único proyecto por pedido confirmado.
* Solo las líneas de servicio participan en el cálculo de horas objetivo.
* La facturación no se recalcula en función de las horas reales imputadas.

Evolución prevista
------------------

* Integración automática con OneDrive para crear carpeta documental.
* Estructuras por fases de auditoría o plantillas por tipo de servicio.
* Roles avanzados apoyados en addons específicos de proyecto.
* Alertas automáticas por umbrales intermedios y cuadros de mando ampliados.
