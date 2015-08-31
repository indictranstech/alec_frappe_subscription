import frappe
import json
from frappe.utils import flt, cint

def get_packing_slip_details(delivery_note, bin_algo_response= None, unique_box_items= None):
    # 1: get packing bin data
    # 2: for each bin create separate packing slip then create the packing deatils
    #    for DN
    if bin_algo_response.get("status") or unique_box_items:
        dn = frappe.get_doc("Delivery Note",delivery_note)

        if delivery_note and bin_algo_response:
            bins_packed = bin_algo_response.get("bins_packed")

            if not bins_packed:
                throw_bin_packing_error(bin_algo_response)
            elif len(bins_packed) > 20:
                frappe.throw("Total number of packages allowed per shipment is 20 \
                            please delete few items and try again")
            else:
                # bins_packed = bins_packed[:20]
                # bins_to_remove = bins_packed[20:]
                # remove_bin_items_from_delivery_note(dn, bins_to_remove)
                dn.set("packing_slip_details",[])
                case_no = 1
                for bin_info in bins_packed:
                    ch = dn.append('packing_slip_details', {})

                    ch.item_code = bin_info.get("bin_data").get("id")
                    ch.item_name = frappe.db.get_value("Item",ch.item_code,"item_name")
                    ch.packing_slip = create_packing_slip(delivery_note, case_no, bin_info)
                    ch.tracking_id = "NA"
                    ch.tracking_status = "Not Packed"
                    case_no += 1

                # freeze the delivery note
                if bin_algo_response.get("not_packed_items"):
                    dn.dn_status = "Parially Packed"
                    items = get_not_packed_items(bin_algo_response.get("not_packed_items"))
                    dn.not_packed_items = json.dumps(items)
                else:
                    dn.dn_status = "Packing Slips Created"

                dn.shipping_overhead_rate = frappe.db.get_value("Shipping Configuration",
                                                                "Shipping Configuration",
                                                                "shipping_overhead")
                dn.save(ignore_permissions=True)
                # return dn
                return {
                    "status": dn.dn_status,
                    "not_packed_items":dn.not_packed_items
                }
    else:
        throw_bin_packing_error(bin_algo_response)

def create_packing_slip(delivery_note, case_no, bin_detail):
    # get items and create the packing slip
    ps = frappe.new_doc("Packing Slip")
    ps.delivery_note = delivery_note
    # case_no = get_recommended_case_no(delivery_note)
    ps.from_case_no, ps.to_case_no = case_no, case_no
    total_weight = flt(bin_detail.get("bin_data").get("weight"))
    ps.net_weight_pkg, ps.gross_weight_pkg = total_weight, total_weight
    ps.package_used = bin_detail.get("bin_data").get("id")
    ps.tracking_id = "NA"
    ps.tracking_status = "Not Packed"

    ps.set("items",[])
    ps.set("bin_items",[])

    items = {}

    # adding items to child table bin items
    for item in bin_detail.get("items"):
        ch_bin_item = ps.append("bin_items",{})
        ch_bin_item.item_code = item.get("id")
        ch_bin_item.item_name = frappe.db.get_value("Item",ch_bin_item.item_code,"item_name")
        ch_bin_item.image_sbs = "<img src='data:image/png;base64,%s'/>"%(item.get("image_sbs"))

        qty = 1
        if items.get(ch_bin_item.item_code):
            qty = items.get(ch_bin_item.item_code) + 1

        items.update({
            ch_bin_item.item_code:qty
        })
    # preparing print format
    ps.bin_packing_info = prepare_images_for_print_format(bin_detail.get("items"))

    # adding items
    for item,qty in items.iteritems():
        ch_item = ps.append("items",{})
        dn_item = frappe.db.get_values("Delivery Note Item",
                                    {"item_code":item,"parent":delivery_note},
                                    ["item_name","stock_uom","description",
                                    "batch_no"], as_dict= True)[0]

        ch_item.item_code = item
        ch_item.item_name = dn_item.get("item_name")
        ch_item.qty = qty
        ch_item.stock_uom = dn_item.get("stock_uom")
        ch_item.description = dn_item.get("description")
        ch_item.batch_no = dn_item.get("batch_no")

    ps.submit()
    return ps.name

def get_recommended_case_no(delivery_note):
    """
        Returns the next case no. for a new packing slip for a delivery
        note
    """
    recommended_case_no = frappe.db.sql("""SELECT MAX(to_case_no) FROM `tabPacking Slip`
        WHERE delivery_note = %s AND docstatus=1""", delivery_note)
    return cint(recommended_case_no[0][0]) + 1

def on_packing_slip_cancel(doc, method):
    # delete the packing slip details entry from delivery note

    delivery_note = doc.delivery_note
    dn = frappe.get_doc("Delivery Note", delivery_note)

    if dn.docstatus == 1:
        frappe.throw("Packing Slip is Linked with Submitted Delivery Note : %s"%dn.name)
    elif dn.docstatus == 0:
        # if dn.dn_status not in "Draft":
        #     frappe.throw("Delivery Note is in Freezed state can not cancel the Packing Slip")
        # else:
        to_remove = []
        for ps in dn.packing_slip_details:
            if ps.packing_slip == doc.name:
                to_remove.append(ps)
        if to_remove:
            [dn.remove(ch) for ch in to_remove]
            if not dn.packing_slip_details:
                dn.dn_status = "Draft"
            dn.save(ignore_permissions = True)

            frappe.delete_doc("Packing Slip",doc.name)

def on_packing_slip_update(doc, method):
    """ update the tracking status on delivery note """
    if doc.track_status == "Manual":
        query = """UPDATE `tabPacking Slip Details` SET tracking_status='%s'
                WHERE parent='%s' AND tracking_id='%s'"""%(doc.tracking_status,
                doc.delivery_note, doc.tracking_id)

        frappe.db.sql(query)

# def remove_bin_items_from_delivery_note(dn_doc, bin_details):
#     # get item info
#     # count item qty and remove or deduct from delivery note items
#     items_qty = {}
#
#     for _bin in bin_details:
#         items = _bin.get("items")
#         for item in items:
#             item_code = item.get("id")
#             items_qty.update({
#                 item_code: (items_qty.get(item_code) or 0) + 1,
#             })
#
#     to_remove = []
#     for row in dn_doc.items:
#         dn_item_code = row.item_code
#         if items_qty.get(dn_item_code):
#             # if delivery note item qty same as bins items qty then delete whole row
#             if row.qty == items_qty.get(dn_item_code):
#                 to_remove.append(row)
#             else:
#                 row.qty -= items_qty.get(dn_item_code):
#
#     [dn_doc.remove(ch) for ch in to_remove]

def throw_bin_packing_error(bin_algo_response):
    msg = "Error occured while creating packing slips\n"
    for error in bin_algo_response.get("errors"):
        if error.get("message"):
            msg += "%s\n"%(error.get("message"))
    frappe.throw(msg)

def get_not_packed_items(not_packed_items):
    items = {}
    for item in not_packed_items:
        items.update({
            item.get("id"): item.get("q")
        })
    return items

def prepare_images_for_print_format(items):
    # ch_bin_item.image_sbs = "<img src='data:image/png;base64,%s'/>"%(item.get("image_sbs"))
    bin_packing_info = ""

    total_items = len(items)
    reqd_row = (total_items // 4) if (total_items % 4 == 0) else (total_items // 4) + 1
    grid_size = 12/total_items if total_items < 4 else 3

    item_count = 0
    for idx in xrange(0, reqd_row):
        bin_packing_info += """<div class="row">"""
        start_idx = idx * 4
        end_idx = start_idx + 4
        for i in xrange(start_idx, end_idx):
            if item_count < total_items:
                bin_packing_info += """<div class="col-xs-%s" align="center">\
                                    <div class="row"><div class="col-xs-12" align="center"><b>%s</b>\
                                    </div></div><div class="row"><div class="col-xs-12">\
                                    <img src='data:image/png;base64,%s'/></div></div><br>\
                                    <div class="row"><div class="col-xs-12" align="center">\
                                    <b>Item :</b> %s</div></div></div>"""%(grid_size,
                                    item_count+1, items[i].get("image_sbs"), items[i].get("id"))
                item_count += 1
            else:
                break

        bin_packing_info += """</div><br>"""

    return bin_packing_info
