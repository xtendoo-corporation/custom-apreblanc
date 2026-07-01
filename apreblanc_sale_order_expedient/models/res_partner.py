# © 2026 Xtendoo Software SLU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_study_entity = fields.Boolean(
        string="Persona/Entidad a Estudiar",
        default=False,
        tracking=True,
        copy=True,
        index=True,
        help=(
            "Indica que este contacto es una persona o entidad objeto de estudio "
            "en el contexto de los expedientes de Apreblanc."
        ),
    )

    birth_or_registration_date = fields.Date(
        string="Fecha de nacimiento / Inscripción de la compañía",
        tracking=True,
        copy=False,
        index=True,
        help=(
            "Fecha de nacimiento para personas o fecha de inscripción para "
            "compañías en el contexto de entidades a estudiar."
        ),
    )

