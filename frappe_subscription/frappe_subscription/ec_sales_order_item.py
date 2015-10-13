import frappe

def validate_items(doc, method):
    # check the item qty
    for item in doc.items:
        if item.qty == 0:
            frappe.throw("%s : Item Qty can not be zero"%item.item_code)
        elif frappe.db.get_value("Item",item.item_code,"item_group") == "Boxes":
            frappe.throw("%s : Can not add the Box Item to Sales Order"%item.item_code)
