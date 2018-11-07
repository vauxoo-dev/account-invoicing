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
            if not old_currency_id or old_currency_id == invoice.currency_id:
                continue
            currency = invoice.with_context(
                date=invoice.date_invoice or fields.Date.today()).currency_id
            rate = old_currency_id._get_conversion_rate(
                old_currency_id, invoice.currency_id, invoice.company_id,
                invoice.date_invoice or fields.Date.today())
            tracking_value_ids = [
                [0, 0, track.create_tracking_values(
                    currency, currency, 'currency_id',
                    self.fields_get(['currency_id'])['currency_id'], 100)],
                [0, 0, track.create_tracking_values(
                    rate, rate,
                    'rate',
                    currency.fields_get(['rate'])['rate'], 100)],
            ]
            self.message_post(
                body=_("Currency updated"),
                subtype='account_invoice_change_currency.mt_currency_update',
                tracking_value_ids=tracking_value_ids,
            )
            from_currency = old_currency_id
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
