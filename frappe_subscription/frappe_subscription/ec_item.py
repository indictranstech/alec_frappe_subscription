import frappe

def validate_dimensions(doc, method):
    height = doc.height
    width = doc.width
    depth = doc.length
    weight = doc.weight_

    if (height <= 0) or (width <= 0) or (depth <= 0) or (weight <= 0):
        frappe.throw("Item's Dimension details should be greater than zero")

    # check the items Dimensions and box Dimensions
    if unique_box_for_packing:
        box = frappe.get_doc("Item", doc.box)
        box_height = box.height
        box_width = box.width
        box_depth = box.length
        box_weight = box.weight_

        if (box_height < height) and (box_width < width) and (box_depth < depth):
            frappe.throw("Given Item can not be fit in selected box")
        elif box_weight < weight:
            frappe.throw("Item weight is greater than Box weight Limit")
