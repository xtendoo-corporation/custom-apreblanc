from . import expedient_return_reason  # Primero las clases sin dependencias
from . import sale_order               # Luego la clase principal
from . import sale_order_expedient_return_history # Finalmente las clases que dependen de sale_order
from . import sale_order_template       # Clases relacionadas con plantillas de pedidos
from . import pre_paid_expedient       # Y por último la nueva clase
from . import pre_paid_expedient_return_history  # Y la clase de devoluciones de expedientes prepagados
from . import account_move
