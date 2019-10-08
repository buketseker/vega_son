# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_confirm(self, merge=True, merge_into=False):
        """ Confirms stock move or put it in waiting if it's linked to another move.
        :param: merge: According to this boolean, a newly confirmed move will be merged
        in another move of the same picking sharing its characteristics.
        """
        move_create_proc = self.env["stock.move"]
        move_to_confirm = self.env["stock.move"]
        move_waiting = self.env["stock.move"]

        to_assign = {}
        for move in self:
            # if the move is preceeded, then it's waiting (if preceeding move is done, then action_assign has been called already and its state is already available)
            if move.move_orig_ids:
                move_waiting |= move
            else:
                check_procure = False
                # Tiny Fix
                if move.procure_method == "make_to_stock":
                    if move.product_id:
                        if move.product_id.route_ids:
                            for route in move.product_id.route_ids:
                                if route.name == "Make To Order + Make To Stock":
                                    check_procure = True

                if move.procure_method == "make_to_order":
                    move_create_proc |= move
                elif check_procure:
                    move_create_proc |= move
                else:
                    move_to_confirm |= move
            if move._should_be_assigned():
                key = (move.group_id.id, move.location_id.id, move.location_dest_id.id)
                if key not in to_assign:
                    to_assign[key] = self.env["stock.move"]
                to_assign[key] |= move

        # create procurements for make to order moves
        for move in move_create_proc:
            values = move._prepare_procurement_values()
            origin = move.group_id and move.group_id.name or (move.origin or move.picking_id.name or "/")
            self.env["procurement.group"].run(
                move.product_id,
                move.product_uom_qty,
                move.product_uom,
                move.location_id,
                move.rule_id and move.rule_id.name or "/",
                origin,
                values,
            )

        move_to_confirm.write({"state": "confirmed"})
        (move_waiting | move_create_proc).write({"state": "waiting"})

        # assign picking in batch for all confirmed move that share the same details
        for moves in to_assign.values():
            moves._assign_picking()
        self._push_apply()
        if merge:
            return self._merge_moves(merge_into=merge_into)
        return self
