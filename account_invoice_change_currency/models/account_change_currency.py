from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def _default_custom_currency_rate(self):
        index_based_currency = (
            self.env.user.company_id.index_based_currency_id)
        if not index_based_currency:
            return 1
        return index_based_currency._convert(
            1, self.env.user.company_id.currency_id, self.env.user.company_id,
            fields.Date.today())

    old_currency_id = fields.Many2one(
        'res.currency', help="The previous currency used")
    index_based_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.index_based_currency_id',
        help="Currency used por reporting purposes",
        readonly=True)
    custom_rate = fields.Float(
        default=_default_custom_currency_rate,
        required=True,
        help="Set new currency rate to apply on the invoice\n."
        "This rate will be taken in order to convert amounts between the "
        "currency on the invoice and MX currency",
        copy=True)

    @api.model
    def create(self, values):
        values['old_currency_id'] = values.get('currency_id')
        return super(AccountInvoice, self).create(values)

    @api.multi
    def action_account_change_currency(self):
        """ This Allows you  Change currency between company currency and
        Invoice currency.
        Firts Case:
            Convert from original currency to MXN(company currency). taking the
            custom rate. e.g.:
                1.- Original USD and New currency are USD
                2.- Covert USD to MXN with custom rate
        Second Case:
            The original Currency was changed to different currency than MXN
            then convert from original currency to MXN, taking default rate
            because custom rate is between new currency and MXN after that
            now convert MXN to new currency taking custom rate. e.g.:
                Original currency USD
                New currency EUR (this has the custom rate EUR vs MXN)
                1.- USD to MXN with default rate
                2.- MXN to EUR with custom rate
        Third Case:
            Original Currency is MXN(company currency) and new currency is any
            different than MXN, e.g.:
                MXN To USD
        """
        for inv in self:
            ctx = dict(company_id=inv.company_id.id, date=inv.date_invoice)
            inv = inv.with_context(ctx)
            old_currency = inv.old_currency_id
            c_currency = inv.company_id.currency_id
            new_currency = inv.currency_id
            custom_rate = 1 / inv.custom_rate
            messages_error = _('Current currency is not configured properly.')
            for line in inv.invoice_line_ids:
                new_price = 0
                final_currency = False
                if c_currency == old_currency and c_currency == new_currency:
                    final_currency = c_currency
                    continue
                # First Case
                if old_currency == new_currency and old_currency != c_currency:
                    new_price = line.price_unit / custom_rate
                    final_currency = c_currency
                    if new_price <= 0:
                        raise ValidationError(messages_error)
                if (old_currency != c_currency and old_currency != new_currency
                        and new_currency == c_currency):
                    raise ValidationError(
                        _("The conversion to %s is automatic.\nIt's not needed"
                          " change currency vaulue, just press the 'Change' "
                          "button.") % new_currency.name)
                # Second Case
                if (old_currency != c_currency and old_currency != new_currency
                        and c_currency not in (old_currency, new_currency)):
                    old_rate = old_currency.rate
                    if old_rate <= 0:
                        raise ValidationError(messages_error)
                    new_price = line.price_unit / old_rate
                    new_price *= custom_rate
                    final_currency = new_currency
                # Third Case
                if old_currency == c_currency and new_currency != c_currency:
                    final_currency = new_currency
                    new_price = line.price_unit * custom_rate
                    if new_price <= 0:
                        raise ValidationError(messages_error)
                line.write({'price_unit': new_price})
            inv.write({'old_currency_id': final_currency.id,
                       'currency_id': final_currency.id})
            # update manual taxes
            for line in inv.tax_line_ids.filtered(lambda x: x.manual):
                line.amount = new_currency.round(line.amount * custom_rate)
            inv.compute_taxes()
            message = _("Currency changed from %s to %s with rate %s") % (
                old_currency.name, new_currency.name, custom_rate)
            inv.message_post(body=message)

    @api.multi
    def finalize_invoice_move_lines(self, move_lines):
        res = super(AccountInvoice, self).finalize_invoice_move_lines(
            move_lines)
        for line in res:
            line[2]['custom_rate'] = self.custom_rate
            line[2]['index_based_currency_rate'] = (
                self.index_based_currency_id._convert(
                    1, self.company_currency_id, self.company_id,
                    self.date_invoice))
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    custom_rate = fields.Float(
        help="This rate will be taken in order to convert amounts between the "
        "currency on the invoice and MXN currency")
    index_based_currency_rate = fields.Float(
        help="This rate will be taken in order to convert amounts between the "
        "Index Based Currency and the Company Curreny")
