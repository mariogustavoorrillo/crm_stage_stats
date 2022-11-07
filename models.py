from odoo import tools, models, fields, api, _
from datetime import datetime


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    is_lost = fields.Boolean('Perdido?')
    is_invoiced = fields.Boolean('Facturado?')
    is_certified = fields.Boolean('Certificado?')

class CrmStageStat(models.Model):
    _name = "crm.stage.stat"
    _description = "crm.stage.stat"

    lead_id = fields.Many2one('crm.lead',string='Lead')
    stage_from_id = fields.Many2one('crm.stage',string='Etapa desde')
    stage_to_id = fields.Many2one('crm.stage',string='Etapa hasta')
    date = fields.Datetime('Fecha')
    diff_days = fields.Integer('Dias')

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def btn_mark_certified(self):
        for rec in self:
            certified_stage = self.env['crm.stage'].search([('is_certified','=',True)])
            if certified_stage:
                rec.stage_id = certified_stage.id

    def write(self, vals):
        stage_from_id = stage_to_id = None
        if 'stage_id' in vals:
            for rec in self:
                stage_from_id = rec.stage_id.id
                stage_to_id = vals.get('stage_id')
        res = super(CrmLead, self).write(vals)
        if stage_from_id and stage_to_id:
            for rec in self:
                prev_stage = self.env['crm.stage.stat'].search([('lead_id','=',rec.id)],order='id desc',limit=1)
                if prev_stage:
                    diff_days = (datetime.now() - prev_stage.date).days
                else:
                    diff_days = (datetime.now() - rec.create_date).days
                vals = {
                        'lead_id': rec.id,
                        'stage_from_id': stage_from_id,
                        'stage_to_id': stage_to_id,
                        'date': str(datetime.now())[:19],
                        'diff_days': diff_days,
                        }
                stat_id = self.env['crm.stage.stat'].create(vals)
        return res

    def _compute_expected_revenue(self):
        for rec in self:
            res = 0
            for sale_order in rec.order_ids:
                res = res + sale_order.amount_total
            rec.expected_revenue = res

    stage_stat_ids = fields.One2many(comodel_name='crm.stage.stat',inverse_name='lead_id',string='Stage stats')
    expected_revenue = fields.Float('Expected Revenue',compute=_compute_expected_revenue)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_cancel(self):
        for rec in self:
            if rec.opportunity_id:
                opportunity_id = rec.opportunity_id
                stage_id = self.env['crm.stage'].search([('is_lost','=',True)],limit=1)
                if stage_id:
                    opportunity_id.stage_id = stage_id.id
        return super(SaleOrder, self).action_cancel()

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for rec in self:
            if rec.opportunity_id:
                opportunity_id = rec.opportunity_id
                opportunity_id.action_set_won()
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped,final=final,date=date)
        for rec in self:
            if rec.opportunity_id:
                stage_invoiced = self.env['crm.stage'].search([('is_invoiced','=',True)])
                if stage_invoiced:
                    opportunity_id = rec.opportunity_id
                    opportunity_id.stage_id = stage_invoiced.id
        return res

    ORDER_STATES = [
        ('draft', 'En proceso'),
        ('sent', 'Presupuesto enviado'),
        ('sale', 'Pedido realizado'),
        ('done', 'Ganada'),
        ('cancel', 'Perdida'),
        ]

    def _compute_itp_state(self):
        for rec in self:
            rec.itp_state = rec.state

    itp_state = fields.Selection(ORDER_STATES, string='ITP Status', 
            readonly=True, copy=False, index=True, tracking=3, default='draft',store=True,compute=_compute_itp_state)
    is_certified = fields.Boolean('Certificado?',default=False)

    def btn_mark_certified(self):
        for rec in self:
            rec.is_certified = True

    def btn_mark_uncertified(self):
        for rec in self:
            rec.is_certified = False
