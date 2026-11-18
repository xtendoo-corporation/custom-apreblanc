# -*- coding: utf-8 -*-
"""Deduplica onedrive_document por onedrive_id antes de crear el indice unico.

Por cada onedrive_id repetido se elige una fila ganadora:
  1. la que esta enlazada a algun pedido (sale_order_onedrive_document_rel),
  2. si no, la de menor id (la mas antigua).
Antes de borrar las copias se reapuntan a la ganadora: parent_id de los hijos,
enlaces con pedidos, mensajes del chatter y actividades. Las filas borradas se
guardan en la tabla onedrive_document_dedup_backup por si hace falta recuperarlas.
"""
import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", (name,))
    return cr.fetchone()[0] is not None


def migrate(cr, version):
    if not _table_exists(cr, 'onedrive_document'):
        return

    cr.execute("""
        SELECT count(*) FROM (
            SELECT onedrive_id FROM onedrive_document
            WHERE onedrive_id IS NOT NULL
            GROUP BY onedrive_id HAVING count(*) > 1
        ) d
    """)
    n_dups = cr.fetchone()[0]
    if not n_dups:
        _logger.info('onedrive_document: sin onedrive_id duplicados')
        return
    _logger.info('onedrive_document: %s onedrive_id duplicados, deduplicando...', n_dups)

    has_rel = _table_exists(cr, 'sale_order_onedrive_document_rel')

    # Mapa perdedora -> ganadora
    cr.execute("DROP TABLE IF EXISTS _onedrive_dedup_map")
    cr.execute("""
        CREATE TEMP TABLE _onedrive_dedup_map ON COMMIT DROP AS
        WITH ranked AS (
            SELECT d.id, d.onedrive_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY d.onedrive_id
                       ORDER BY %s d.id
                   ) AS rn
            FROM onedrive_document d
            WHERE d.onedrive_id IS NOT NULL
        )
        SELECT l.id AS loser_id, w.id AS winner_id
        FROM ranked l
        JOIN ranked w ON w.onedrive_id = l.onedrive_id AND w.rn = 1
        WHERE l.rn > 1
    """ % ("(EXISTS (SELECT 1 FROM sale_order_onedrive_document_rel r "
           "WHERE r.onedrive_document_id = d.id)) DESC," if has_rel else ""))
    cr.execute("CREATE INDEX ON _onedrive_dedup_map (loser_id)")
    cr.execute("SELECT count(*) FROM _onedrive_dedup_map")
    n_losers = cr.fetchone()[0]

    # Copia de seguridad de las filas que se van a borrar
    cr.execute("DROP TABLE IF EXISTS onedrive_document_dedup_backup")
    cr.execute("""
        CREATE TABLE onedrive_document_dedup_backup AS
        SELECT d.*, m.winner_id AS dedup_winner_id
        FROM onedrive_document d JOIN _onedrive_dedup_map m ON m.loser_id = d.id
    """)

    # 1. Hijos: reapuntar parent_id (si el padre es una copia perdedora)
    cr.execute("""
        UPDATE onedrive_document c SET parent_id = m.winner_id
        FROM _onedrive_dedup_map m WHERE c.parent_id = m.loser_id
    """)

    # 2. Enlaces con pedidos de venta
    if has_rel:
        cr.execute("""
            INSERT INTO sale_order_onedrive_document_rel (sale_order_id, onedrive_document_id)
            SELECT DISTINCT r.sale_order_id, m.winner_id
            FROM sale_order_onedrive_document_rel r
            JOIN _onedrive_dedup_map m ON m.loser_id = r.onedrive_document_id
            ON CONFLICT DO NOTHING
        """)
        cr.execute("""
            DELETE FROM sale_order_onedrive_document_rel r
            USING _onedrive_dedup_map m WHERE r.onedrive_document_id = m.loser_id
        """)

    # 3. Chatter, actividades, seguidores y adjuntos
    cr.execute("""
        UPDATE mail_message x SET res_id = m.winner_id
        FROM _onedrive_dedup_map m
        WHERE x.model = 'onedrive.document' AND x.res_id = m.loser_id
    """)
    cr.execute("""
        UPDATE mail_activity x SET res_id = m.winner_id
        FROM _onedrive_dedup_map m
        WHERE x.res_model = 'onedrive.document' AND x.res_id = m.loser_id
    """)
    cr.execute("""
        DELETE FROM mail_followers x USING _onedrive_dedup_map m
        WHERE x.res_model = 'onedrive.document' AND x.res_id = m.loser_id
    """)
    cr.execute("""
        DELETE FROM ir_attachment x USING _onedrive_dedup_map m
        WHERE x.res_model = 'onedrive.document' AND x.res_id = m.loser_id
    """)

    # 4. Borrar copias
    cr.execute("""
        DELETE FROM onedrive_document d USING _onedrive_dedup_map m WHERE d.id = m.loser_id
    """)
    _logger.info('onedrive_document: %s copias eliminadas (respaldo en onedrive_document_dedup_backup)', n_losers)
