# Copyright 2017-2018 Vauxoo
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import fields, models, api
from odoo.tools import float_compare


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    custom_rate = fields.Float(
        digits=(12, 6),
        default=1,
        help="Set new currency rate to apply on the invoice\n."
        "This rate will be taken in order to convert amounts between the "
        "currency on the invoice and last currency")

    @api.multi
    def action_account_change_currency(self):
        track = self.env['mail.tracking.value']
        precision = self.env['decimal.precision'].precision_get(
            'Payment Terms')
        today = fields.Date.today()
        for invoice in self.filtered(lambda x: x.state == 'draft'):
            from_currency = invoice.get_last_currency_id()
            if not from_currency:
                continue
            if not invoice.date_invoice:
                invoice.date_invoice = today
            ctx = {'company_id': invoice.company_id.id,
                   'date': invoice.date_invoice}
            currency = invoice.with_context(**ctx).currency_id
            currency_skip = invoice.get_last_currency_id(True)
            old_rate_currency, old_rate = invoice.get_last_rate()
            new_rate = invoice.custom_rate
            if not invoice.custom_rate:
                new_rate = currency.with_context(**ctx)._get_conversion_rate(
                    currency_skip, currency, invoice.company_id,
                    invoice.date_invoice) if from_currency else None
            if (old_rate_currency == currency and new_rate
                    and old_rate and float_compare(
                        new_rate, old_rate, precision_digits=precision) == 0):
                if not invoice.custom_rate:
                    continue
                new_rate = currency.with_context(**ctx)._get_conversion_rate(
                    currency_skip, currency, invoice.company_id,
                    invoice.date_invoice) if from_currency else None
                if float_compare(
                        new_rate, old_rate, precision_digits=precision) == 0:
                    continue
                invoice.custom_rate = new_rate

            rate = currency.with_context(**ctx)._get_conversion_rate(
                from_currency, currency, invoice.company_id,
                invoice.date_invoice)
            if from_currency == currency and old_rate and new_rate != old_rate:
                rate = new_rate / old_rate
            if from_currency != currency:
                rate = new_rate
            tracking_value_ids = [
                [0, 0, track.create_tracking_values(
                    currency, currency, 'currency_id',
                    self.fields_get(['currency_id'])['currency_id'], 100)],
                [0, 0, track.create_tracking_values(
                    new_rate, new_rate, 'rate',
                    currency.fields_get(['rate'])['rate'], 100)],
            ]
            self.message_post(
                subtype='account_invoice_change_currency.mt_currency_update',
                tracking_value_ids=tracking_value_ids)
            for line in invoice.invoice_line_ids:
                line.price_unit *= rate
            for tax in invoice.tax_line_ids:
                tax.amount *= rate

    @api.onchange('currency_id', 'date_invoice')
    def _onchange_currency_change_rate(self):
        last_currency = self.get_last_currency_id()
        if last_currency == self.currency_id:
            last_currency = self.get_last_currency_id(True)
            if last_currency == self.currency_id:
                last_currency = self.get_last_rate()[0]
        if not (self.currency_id and last_currency):
            last_currency = self.company_currency_id
        today = fields.Date.today()
        ctx = {'company_id': self.company_id.id,
               'date': self.date_invoice or today}
        self.custom_rate = last_currency.with_context(
            **ctx)._get_conversion_rate(
                last_currency, self.currency_id, self.company_id,
                self.date_invoice or today)

    @api.multi
    def get_last_currency_id(self, skip_update_currency=False):
        self.ensure_one()
        subtype_id = self.env.ref(
            'account_invoice_change_currency.mt_currency_update')
        subtype_create_id = self.env.ref('account.mt_invoice_created')
        domain = [
            ('mail_message_id', 'in', self.message_ids.ids),
            ('field', '=', 'currency_id'),
        ]
        if skip_update_currency:
            domain += [('mail_message_id.subtype_id', '!=', subtype_id.id)]
        last_value = self.env['mail.tracking.value'].sudo().search(
            domain, limit=1, order='write_date desc, id desc')
        value = last_value.old_value_integer
        if last_value.mail_message_id.subtype_id == subtype_create_id:
            value = last_value.new_value_integer
        return self.currency_id.browse(value)

    @api.multi
    def get_last_rate(self):
        self.ensure_one()
        last_values = self.env['mail.tracking.value'].sudo().search([
            ('mail_message_id', 'in', self.message_ids.ids),
            ('field', 'in', ['rate', 'currency_id']),
        ], limit=2, order='write_date desc, id desc')
        # if rate and currency come from same message_id
        if (len(last_values) == 2 and last_values[0].mail_message_id ==
                last_values[1].mail_message_id):
            currency_value, rate_value = sorted(last_values,
                                                key=lambda r: r.field)
            return (self.currency_id.browse(currency_value.old_value_integer),
                    rate_value.old_value_float)
        return self.currency_id.browse(None), None
