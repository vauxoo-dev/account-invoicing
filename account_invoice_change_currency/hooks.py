import logging
from openerp import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    cr.execute('ALTER TABLE account_invoice ADD COLUMN custom_rate numeric;')

    # /!\ NOTE: This second clause can be improved. Instead of using a plain 1
    cr.execute('UPDATE account_invoice SET custom_rate=1;')
