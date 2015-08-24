import frappe

def validate_dimensions(doc, method):
    height = doc.height
    width = doc.width
    depth = doc.length
    weight = doc.weight_

    if (height <= 0) or (width <= 0) or (depth <= 0) or (weight <= 0):
        frappe.throw("Item's Dimension details should be greater than zero")
