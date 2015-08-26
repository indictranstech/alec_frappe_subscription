import frappe

def validate_items(doc, method):
    # check the item qty
    for item in doc.items:
        if item.qty == 0:
            frappe.throw("%s : Item Qty can not be zero"%item.item_code)
