# Copyright 2017-2018 Vauxoo
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import fields, models, api, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_account_change_currency(self):
        track = self.env['mail.tracking.value']
        for invoice in self.filtered(lambda x: x.state == 'draft'):
            old_currency_id = invoice.get_last_currency_id()
            if not old_currency_id:
                continue
            old_rate_currency, old_rate = invoice.get_last_rate()
            new_rate = old_currency_id._get_conversion_rate(
                old_currency_id, invoice.currency_id, invoice.company_id,
                invoice.date_invoice or fields.Date.today()) if old_currency_id else None
            if (old_rate_currency == invoice.currency_id and new_rate
                    and old_rate and new_rate == old_rate):
                continue
            new_rate_diff = None
            if new_rate != old_rate:
                new_rate_diff = new_rate / old_rate

            # old_currency_id == invoice.currency_id:
            currency = invoice.with_context(
                date=invoice.date_invoice or fields.Date.today()).currency_id
            if new_rate_diff:
                currency._cache['rate'] = new_rate_diff
            tracking_value_ids = [
                [0, 0, track.create_tracking_values(
                    currency, currency, 'currency_id',
                    self.fields_get(['currency_id'])['currency_id'], 100)],
                [0, 0, track.create_tracking_values(
                    new_rate, new_rate,
                    'rate',
                    currency.fields_get(['rate'])['rate'], 100)],
            ]
            self.message_post(
                body=_("Currency updated"),
                subtype='account_invoice_change_currency.mt_currency_update',
                tracking_value_ids=tracking_value_ids,
            )
            for line in invoice.invoice_line_ids:
                line.price_unit = from_currency._convert(
                    line.price_unit, invoice.currency_id,
                    invoice.company_id,
                    invoice.date_invoice or fields.Date.today())
            for tax in invoice.tax_line_ids:
                tax.amount = from_currency._convert(
                    tax.amount, invoice.currency_id, invoice.company_id,
                    invoice.date_invoice or fields.Date.today())

    @api.model
    def get_last_currency_id(self):
        self.ensure_one()
        last_value = self.env['mail.tracking.value'].search([
            ('mail_message_id', 'in', self.message_ids.ids),
            ('field', '=', 'currency_id'),
        ], limit=1, order='write_date desc, id desc')
        return self.currency_id.browse(last_value.old_value_integer)

    @api.multi
    def get_last_rate(self):
        self.ensure_one()
        last_values = self.env['mail.tracking.value'].search([
            ('mail_message_id', 'in', self.message_ids.ids),
            ('field', 'in', ['rate', 'currency_id']),
        ], limit=2, order='write_date desc, id desc')
        # if rate and currency come from same message_id
        if (len(last_values) == 2 and
            last_values[0].mail_message_id == last_values[1].mail_message_id):
            currency_value, rate_value = sorted(last_values,
                                                key=lambda r: r.field)
            return (self.currency_id.browse(currency_value.old_value_integer),
                    rate_value.old_value_float)
        return self.currency_id.browse(None), None

