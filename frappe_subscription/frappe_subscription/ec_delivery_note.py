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
        remove_shipping_overhead(doc)
        [frappe.delete_doc("Packing Slip Details",ch.name, ignore_permissions=True) for ch in ch_to_remove]
        [frappe.delete_doc("Packing Slip", ps_name, ignore_permissions=True) for ps_name in ps_to_cancel]

        doc.dn_status = "Draft"
        doc.boxes_stock_entry = ""

def on_delivery_note_submit(doc, method):
    # check packing slips
    # check if rates are fetched if not fist get ups rates

    if doc.dn_status == "Draft":
        frappe.throw("Bin Packing Information Not Found ...")
    elif doc.dn_status == "Partialy Packed":
        frappe.throw("Packing Slip are not created for all items. Please create packing slips first")

    if  doc.is_manual_shipping == 0:
        #TODO remove if condition
        condition = is_shipping_overhead_available(doc)

        if (doc.dn_status == "Packing Slips Created") or (not condition):
            frappe.throw("First Add the Shipping Overhead")

        get_shipping_labels(doc)
    else:
        # validate if shipping overhead is calculated
        validate_update_packing_slip_details(doc)

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

def get_shipping_overhead_amount(doc):
    overhead = 0
    params = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                        ["default_account","cost_center"], as_dict=True)[0]
    if not doc.taxes:
        return overhead
    else:
        for tax in doc.taxes:
            if tax.charge_type == "Actual" and tax.account_head == params.get("default_account") and tax.cost_center == params.get("cost_center"):
                overhead = tax.tax_amount
                break
        return overhead

def get_shipping_overhead_row(doc):
    row = None
    params = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                        ["default_account","cost_center"], as_dict=True)[0]
    if not doc.taxes:
        return overhead
    else:
        for tax in doc.taxes:
            if tax.charge_type == "Actual" and tax.account_head == params.get("default_account") and tax.cost_center == params.get("cost_center"):
                row = tax
                break
        return row

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

def validate(doc, method):
    validate_address(doc)
    validate_manual_shipping_rates(doc)

def validate_address(doc):
    if not doc.shipping_address_name:
        frappe.throw("Shipping Address is required")

def validate_manual_shipping_rates(doc):
    if doc.is_manual_shipping:
        if doc.carrier_shipping_rate > 0:
            tax_amount = get_shipping_overhead_amount(doc)
            overhead = doc.total_shipping_rate
            if tax_amount:
                if tax_amount != overhead:
                    frappe.throw("Shipping Charges and Total Shipping Rates does not match")
            else:
                frappe.throw("Shipping Charges is not added ..")
        else:
            frappe.throw("Carrier Shipping Rate can not be Zero")

def validate_update_packing_slip_details(doc):
    condition = is_shipping_overhead_available(doc)

    if doc.carrier_shipping_rate and condition:
        # Update tracking id and tracking status on packing slip
        for ps_details in doc.packing_slip_details:
            if ps_details.tracking_id == "NA":
                frappe.throw("Tracking ID can not be set to 'NA', Please update the tracking ID")
            else:
                update_packing_slip(ps_details.tracking_id, ps_details.tracking_status, ps_details.packing_slip)
    else:
        frappe.throw("First Add the Shipping Charges")

def update_packing_slip(tracking_id, tracking_status, packing_slip):
    query = """UPDATE `tabPacking Slip` SET tracking_id='%s', tracking_status='%s',
            track_status='Manual' WHERE name='%s'"""%(tracking_id, tracking_status,
            packing_slip)
    frappe.db.sql(query)

def on_update_after_submit(doc, method):
    for ps_details in doc.packing_slip_details:
        update_packing_slip(ps_details.tracking_id, ps_details.tracking_status, ps_details.packing_slip)
