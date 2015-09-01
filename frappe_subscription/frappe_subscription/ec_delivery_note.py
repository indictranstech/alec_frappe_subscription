import frappe
import json
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
        remove_shipping_overhead()
        [frappe.delete_doc("Packing Slip Details",ch.name) for ch in ch_to_remove]
        [frappe.delete_doc("Packing Slip", ps_name) for ps_name in ps_to_cancel]

        doc.dn_status = "Draft"
        doc.boxes_stock_entry = ""

def on_delivery_note_submit(doc, method):
    # check packing slips
    # check if rates are fetched if not fist get ups rates

    if doc.dn_status == "Draft":
        frappe.throw("Bin Packing Information Not Found ...")
    elif doc.dn_status == "Partialy Packed":
        frappe.throw("Packing Slip are not created for all items. Please crate packing slips first")

    if  doc.is_manual_shipping == 0:
        # get_shipping_rates(doc.name) if doc.dn_status == "Packing Slips Created" else get_shipping_labels(doc)
        condition = is_shipping_overhead_available(doc)

        if (doc.dn_status == "Packing Slips Created") or (not condition):
            # get_shipping_rates(doc.name)
            frappe.throw("First Add the Shipping Overhead")

        get_shipping_labels(doc)
    else:
        # validate if shipping overhead is calculated
        condition = is_shipping_overhead_available(doc)

        if doc.carrier_shipping_rate and condition:
            # Update tracking id and tracking status on packing slip
            for ps_details in doc.packing_slip_details:
                query = """UPDATE `tabPacking Slip` SET tracking_id='%s', tracking_status='%s',
                        track_status='Manual' WHERE name='%s'"""%(ps_details.tracking_id,
                        ps_details.tracking_status, ps_details.packing_slip)
                frappe.db.sql(query)
        else:
            frappe.throw("First Add the Shipping Overhead")

def is_shipping_overhead_available(doc):
    condition = False
    params = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                        ["default_account","cost_center"], as_dict=True)[0]
    if not doc.taxes:
        return condition
    else:
        for tax in doc.taxes:
            if tax.charge_type == "Actual" and tax.account_head == params.get("default_account") and tax.cost_center == params.get("cost_center"):
                condition = True
                break
        return condition

def remove_shipping_overhead(doc):
    to_remove = []

    if doc.taxes:
        params = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                            ["default_account","cost_center"], as_dict=True)[0]
        for tax in doc.taxes:
            if tax.charge_type == "Actual" and tax.account_head == params.get("default_account") and tax.cost_center == params.get("cost_center"):
                to_remove.append(tax)
        [doc.remove(tx) for tx in to_remove]
        doc.carrier_shipping_rate = 0.0
        doc.total_shipping_rate = 0.0
        doc.total_taxes_and_charges = 0.0
        doc.grand_total = 0.0
        doc.in_words = ""
        doc.ups_rates = json.dumps({})

def validate_address(doc, method):
    if not doc.shipping_address_name:
        frappe.throw("Shipping address required")
    # if dn_status is shipping rates fetched then remove shipping overhead and set ups_rates = {}
    if doc.dn_status == "UPS Rates Fetched":
        remove_shipping_overhead(doc)
        doc.dn_status = "Packing Slips Created"
        doc.save(ignore_permissions=True)
