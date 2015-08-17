import frappe
from frappe_subscription.frappe_subscription.ups_shipping_rates import get_shipping_rates
from frappe_subscription.frappe_subscription.ups_shipping_package import get_shipping_labels

def on_delivery_note_cancel(doc, method):
    # check the freeze state of the delivery note
    # cancel and delete all the packing slip

    # check if linked with stock entry
    se_docstatus = frappe.db.get_value("Stock Entry",doc.boxes_stock_entry, "docstatus")

    if se_docstatus and se_docstatus != 2:
        frappe.throw("First Cancel the Stock Entry : %s "%(doc.boxes_stock_entry))
    else:
        # delete the packing slips
        ps_to_cancel = []
        ch_to_remove = []
        bin_items = {}

        for ps_details in doc.packing_slip_details:
            ps_to_cancel.append(ps_details.packing_slip)
            bin_qty = (bin_items.get(ps_details.item_code) or 0) + 1
            bin_items.update({
                ps_details.item_code:bin_qty
            })
            ch_to_remove.append(ps_details)

        [doc.remove(ch) for ch in ch_to_remove]
        [frappe.delete_doc("Packing Slip Details",ch.name) for ch in ch_to_remove]
        [frappe.delete_doc("Packing Slip", ps_name) for ps_name in ps_to_cancel]

        doc.dn_status = "Draft"
        doc.boxes_stock_entry = ""

def on_delivery_note_submit(doc, method):
    # check packing slips
    # check if rates are fetched if not fist get ups rates

    if doc.dn_status == "Draft":
        frappe.throw("Bin Packing Information Not Found ...")
    if  doc.is_manual_shipping == 0:
        # get_shipping_rates(doc.name) if doc.dn_status == "Packing Slips Created" else get_shipping_labels(doc)
        if doc.dn_status == "Packing Slips Created":
            get_shipping_rates(doc.name)
        validate_address(doc)
        get_shipping_labels(doc)

def validate_address(doc):
    if not doc.shipping_address_name:
        frappe.throw("Shipping address required")
