Apreblanc Service Project Control
=================================

Resumen funcional
-----------------

Este módulo añade un control operativo para servicios vendidos desde pedidos de
venta estándar en Odoo.

Cuando se confirma un pedido con líneas cuyo producto tiene marcada la casilla
``Crear proyecto operativo``:

* se crea un proyecto operativo asociado al pedido,
* se genera una tarea por cada línea marcada,
* se encadenan las tareas en el mismo orden del presupuesto cuando hay varias anualidades o hitos,
* se calcula una bolsa de horas objetivo en función del producto y la cantidad,
* se monitoriza el consumo horario real mediante partes de horas,
* cada parte de horas conserva la fase operativa de la tarea en el momento de imputar,
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

* En la ficha del producto debe marcarse la casilla ``Crear proyecto operativo``.
  Esta casilla es visible en cualquier tipo de producto, no solo en servicios.
* En la ficha del producto debe informarse el campo ``Horas objetivo servicio``.
* El usuario que vaya a imputar horas debe poder usar partes de horas en
  proyecto.
* El pedido de venta debe seguir el flujo estándar de confirmación.

Campos que añade el módulo
--------------------------

``product.template``
    Casilla ``Crear proyecto operativo`` que, al estar marcada, hace que las
    líneas de ese producto generen proyecto y tareas al confirmar el pedido.
    Es independiente del tipo de producto.
    Campo ``Horas objetivo servicio`` para definir las horas previstas por cada
    unidad vendida.

``sale.order.line``
    Campo calculado ``Horas objetivo`` en función de cantidad por horas objetivo
    del producto, solo para líneas cuyo producto tiene la casilla marcada.

``sale.order``
    Enlace al ``Proyecto operativo`` y métricas agregadas de control horario.

``project.project``
    Marcador de control Apreblanc, pedido origen, responsables y métricas de
    horas, desviación y rentabilidad.

``project.task``
  Trazabilidad con la línea del pedido que originó la tarea y fase operativa
  de auditoría.

``account.analytic.line``
  Validación del límite horario antes de aceptar nuevas imputaciones y copia
  de la fase de la tarea sobre la imputación.

Manual de uso
-------------

1. Crear o revisar el producto.

   * Abrir el producto.
   * Marcar la casilla ``Crear proyecto operativo``.
   * Indicar el valor de ``Horas objetivo servicio``.
   * Guardar el producto.

2. Crear el pedido de venta.

   * Añadir una o varias líneas con productos marcados.
   * La métrica de horas previstas se calculará automáticamente en cada línea.

3. Confirmar el pedido.

   * Al confirmar, el módulo crea un único proyecto operativo para el pedido.
   * También crea una tarea por cada línea cuyo producto está marcado.
   * En el pedido aparece el botón ``Proyecto operativo``.

4. Gestionar el proyecto.

   * Desde el proyecto se visualizan las horas presupuestadas, consumidas,
     restantes, desviación, rentabilidad y estado.
   * El proyecto conserva un enlace directo al pedido origen.
   * Puede informarse el jefe de proyecto, gestor junior y gestor senior.
   * Las tareas arrancan en la fase ``Preparacion`` y avanzan por las cuatro
     fases estándar: preparación, recogida de información, análisis e informe.
   * Si el pedido tiene varias líneas de servicio, cada tarea posterior queda
     bloqueada por la anterior hasta que esta se complete.

5. Imputar horas.

   * Las horas se registran en tareas del proyecto mediante partes de horas.
   * La descripción del parte incorpora automáticamente la fase activa de la
     tarea para facilitar el análisis posterior.
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
* la generación de tareas desde las líneas cuyo producto está marcado,
* que un producto marcado genera proyecto y tareas aunque no sea de tipo servicio,
* que las líneas no marcadas no generan proyecto ni tareas,
* el encadenado de dependencias entre tareas sucesivas,
* el cálculo de horas objetivo trasladado al proyecto,
* la inclusión de la fase operativa en la imputación de horas,
* el bloqueo de imputaciones al superar el objetivo,
* la continuidad del registro horario tras la autorización del exceso.

Límites actuales
----------------

* El módulo crea un único proyecto por pedido confirmado.
* Solo las líneas cuyo producto tiene marcada la casilla ``Crear proyecto
  operativo`` participan en la creación de tareas y en el cálculo de horas
  objetivo.
* La facturación no se recalcula en función de las horas reales imputadas.

Evolución prevista
------------------

* Integración automática con OneDrive para crear carpeta documental.
* Plantillas específicas por tipo de servicio o expediente.
* Roles avanzados apoyados en addons específicos de proyecto.
* Alertas automáticas por umbrales intermedios y cuadros de mando ampliados.
