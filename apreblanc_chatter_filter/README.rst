Apreblanc Chatter Filter
========================

Este módulo filtra los mensajes de seguimiento (tracking) de campos económicos en el chatter, 
permitiendo que solo los usuarios pertenecientes al grupo **"Ver mensajes económicos en chatter"** 
puedan verlos, mientras que el resto de empleados no los visualizan.

**Importante**: Los mensajes se siguen generando y almacenando en base de datos. El filtro solo 
controla su visibilidad mediante una regla de registro (`ir.rule`), garantizando trazabilidad completa.

Funcionalidades
===============

- Crea un subtipo de mensaje dedicado (`mt_economic_change`) para cambios en campos económicos
- Implementa lógica en modelos objetivo para detectar cambios en campos económicos:
  - ``sale.order``
  - ``sale.order.line``
  - ``account.move``
- Define dos reglas de registro sobre `mail.message`:
  1. **Regla de ocultación**: Usuarios normales (`base.group_user`) no ven mensajes con el subtipo económico
  2. **Regla de acceso**: Solo usuarios en el grupo "Ver mensajes económicos en chatter" ven los mensajes
- Respeta la jerarquía de grupos: los usuarios en el grupo "Ver mensajes económicos en chatter" 
  ven todos los mensajes (regla permisiva); el resto no

Campos económicos monitorados
=============================

- ``amount_total`` (Importe total)
- ``amount_tax`` (Importe de impuestos)
- ``amount_untaxed`` (Importe sin impuestos)

Instalación
===========

1. Clona o descarga el módulo en el directorio de módulos personalizados:
   
   ```bash
   git clone <repo-url>/apreblanc_chatter_filter \
     odoo/custom/src/custom-apreblanc/apreblanc_chatter_filter
   ```

2. Instala o actualiza el módulo en Odoo:
   
   **Línea de comandos (Doodba)**:
   
   ```bash
   python manage.py -u apreblanc_chatter_filter
   ```
   
   **O vía interfaz web**:
   - Accede a *Aplicaciones*
   - Busca "Apreblanc Chatter Filter"
   - Haz clic en "Instalar"

3. (Opcional) Para actualizar tras cambios:
   
   ```bash
   python manage.py -u apreblanc_chatter_filter --reload-addons
   ```

Limitaciones conocidas
======================

1. **Agrupación de cambios en un mismo guardado (write)**:
   
   - ``_track_subtype()`` devuelve un único subtipo por cada operación de escritura
   - Si un mismo guardado modifica a la vez un campo económico **y** un campo no económico,
     ambos cambios se agrupan en un solo mensaje con el subtipo económico (`mt_economic_change`)
   - **Consecuencia**: Los usuarios sin acceso de contabilidad no verán ni el cambio económico ni el no económico
   - **Solución futura**: Separar cambios en múltiples mensajes o permitir múltiples subtypes por write
     (requeriría cambios en el core de Odoo)

2. **Bypass con sudo() y superusuario**:
   
   - Las reglas ``ir.rule`` se aplican a través de la capa ACL de Odoo
   - El código que ejecuta en ``sudo()`` o llamadas del superusuario se salta las reglas
   - **Implicación**: El sistema interno que publica mensajes seguirá funcionando correctamente
   - **Nota**: Esto es comportamiento estándar de Odoo y es necesario para el correcto funcionamiento

3. **Rendimiento con volumen alto**:
   
   - ``mail.message`` es un modelo muy transitado en Odoo (usado por chatter, Discuss, notificaciones, etc.)
   - El filtro se aplica a **todas** las lecturas de `mail.message` en el sistema
   - **Recomendación**: Valida el rendimiento en un entorno de producción con volumen realista
   - La regla está acotada al subtipo económico, lo que minimiza el impacto

4. **Asignación del grupo personalizado**:
   
   - En Odoo Community, el grupo "Ver mensajes económicos en chatter" está disponible 
     bajo la categoría *Contabilidad* en la interfaz de usuarios
   - Para que un usuario vea los mensajes económicos, simplemente hay que asignarle 
     este grupo en su perfil (Usuarios > Roles/Grupos)

Arquitectura
============

**Estructura del módulo**:

```
apreblanc_chatter_filter/
├── __init__.py                         # Importaciones del módulo
├── __manifest__.py                     # Metadatos e instrucciones de carga
├── models/
│   ├── __init__.py
│   ├── sale_order.py                   # Herencia de sale.order
│   ├── sale_order_line.py              # Herencia de sale.order.line
│   └── account_move.py                 # Herencia de account.move
├── data/
│   └── mail_message_subtype.xml        # Definición del subtipo económico
├── security/
│   └── mail_message_rules.xml          # Reglas de lectura sobre mail.message
└── README.rst                          # Este archivo
```

**Flujo de funcionamiento**:

1. Al guardar cambios en un registro (sale.order, account.move, etc.)
2. Se llama a ``_track_subtype()`` con los campos modificados
3. Si algún campo está en la lista de campos económicos (`amount_*`)
4. Se retorna el subtipo `mt_economic_change`
5. Al generar el mensaje en el chatter, se asigna ese subtipo
6. Cuando el usuario lee el chatter, ``mail.message`` filtra por ``ir.rule``:
   - Usuario sin contabilidad: ve solo mensajes sin subtipo o con subtipo diferente
   - Usuario con ``account.group_account_user``: ve todos los mensajes (regla permisiva)

Decisiones técnicas
===================

**¿Por qué un subtype único y no uno por modelo?**

- Un subtype genérico (`mt_economic_change` sin `res_model` específico) simplifica el mantenimiento
- Evita duplicación de reglas (una regla aplica a los 3 modelos)
- Facilita futuras extensiones con modelos adicionales

**¿Por qué usar `eval="ref()"` en las reglas?**

- Las reglas se evalúan en tiempo de ejecución, no en tiempo de instalación
- El ``ref()`` estándar no está disponible en esa evaluación
- Se usa `eval="ref(...)"` para resolver el id del subtype **en instalación** 
  y guardar el id numérico en la base de datos
- Esto garantiza que la regla funcione correctamente aunque el subtipo se desinstale y reinstale

Plan de pruebas manual
======================

### Test 1: Usuario SIN acceso de Contabilidad Completa

**Requisito previo**:
- Crear o usar un usuario con rol "Employee" sin grupo `account.group_account_user`

**Pasos**:

1. Inicia sesión como este usuario
2. Abre un registro de tipo `sale.order`, `sale.order.line` o `account.move`
3. Modifica un campo económico (ej: **Descuento** → $50, o **Cantidad** → 5)
4. Guarda los cambios
5. Observa el chatter

**Resultado esperado**:

- El mensaje de tracking del cambio económico **NO aparece** en el chatter
- Otros mensajes/notas normales **SÍ se ven** (confirma que el chatter funciona en general)

### Test 2: Usuario CON acceso de Contabilidad Completa

**Requisito previo**:
- Usar un usuario con grupo `account.group_account_user`
- (Suele ser el usuario admin o contables)

**Pasos**:

1. Inicia sesión como este usuario
2. Abre el **mismo registro** del Test 1
3. Observa el chatter

**Resultado esperado**:

- El mensaje de tracking económico **SÍ aparece** en el chatter
- El mensaje muestra los campos modificados y sus valores anteriores/nuevos

### Test 3: Verificar trazabilidad en base de datos

**Objetivo**: Confirmar que el mensaje existe en BD independientemente de la visibilidad

**Pasos**:

1. Accede a la base de datos Odoo (como admin o superusuario)
2. Ejecuta una consulta SQL (o usa el modo SQL de Odoo):
   
   ```sql
   SELECT id, message_type, subtype_id, body, create_date
   FROM mail_message
   WHERE subtype_id IN (
       SELECT id FROM mail_message_subtype 
       WHERE name = 'Economic Amount Change'
   )
   ORDER BY create_date DESC
   LIMIT 10;
   ```

3. Verifica que aparecen registros `mail.message` con `subtype_id` apuntando al subtipo económico

**Resultado esperado**:

- Los registros existen en la tabla `mail_message`
- Tienen la hora de creación correcta (matching con el cambio del Test 1)
- Confirma que la generación/almacenamiento es ininterrumpido

### Test 4: Agrupación de cambios en el mismo write

**Objetivo**: Documentar el comportamiento cuando un mismo guardado toca campos económicos y no económicos

**Pasos**:

1. Abre un registro (sale.order, account.move)
2. **En el mismo guardado** (una sola vez que presiones Guardar):
   - Modifica un campo económico (ej: descuento/impuesto)
   - Modifica un campo no económico (ej: notas internas, dirección, etc.)
3. Guarda

**Resultado esperado**:

- Se genera **un solo mensaje** de tracking
- El mensaje tiene subtipo `mt_economic_change` (porque uno de los campos es económico)
- El usuario sin contabilidad **no ve el mensaje** (incluidos ambos cambios)
- El mensaje detalla todos los campos modificados (económicos y no económicos)

**Documentación**: Este es el comportamiento conocido. Para separar cambios, se requerirían 
cambios en el core de Odoo o una solución más compleja en el hook de `_track_subtype()`.

Soporte y contribuciones
========================

Para reportar issues o contribuir al módulo, contacta a:

- **Xtendoo** (https://www.xtendoo.es)
- **Correo**: info@xtendoo.es

Historial de cambios
====================

**19.0.1.0.0** (Inicial)

- Implementación inicial del módulo
- Soporte para ``sale.order``, ``sale.order.line``, ``account.move``
- Reglas de registro para filtrado por grupo de contabilidad

Licencia
========

**LGPL-3** (GNU Lesser General Public License v3.0)

Para más información, consulta el archivo `LICENSE` o https://www.gnu.org/licenses/lgpl-3.0.html
