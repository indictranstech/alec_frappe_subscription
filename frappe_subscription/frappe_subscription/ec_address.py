import frappe

def validate_address(doc, method):
    if not doc.state:
        frappe.throw("Please mention the State Province Code in state field")
    elif not doc.pincode:
        frappe.throw("Please mention the pin code")
