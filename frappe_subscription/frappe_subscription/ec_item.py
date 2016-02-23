import frappe

def validate(doc, method):
    validate_uom_conversions(doc)
    validate_dimensions(doc)

def validate_uom_conversions(doc):
    count = 0
    count = sum(map(lambda item: item.default_shipping_uom, doc.uoms))
    if not count:
        frappe.throw("Please first select the default UOM Conversion Details")

# def validate_dimensions(doc):
#     height = doc.height
#     width = doc.width
#     depth = doc.length
#     weight = doc.weight_

#     if (height < 0) or (width < 0) or (depth < 0) or (weight < 0): 
#             frappe.throw("Item's Dimension details cannot be negative.")

#     # check the items Dimensions and box Dimensions
#     if doc.unique_box_for_packing:
#         box = frappe.get_doc("Item", doc.box)
#         box_height = box.height
#         box_width = box.width
#         box_depth = box.length
#         box_weight = box.weight_

#         if (box_height < height) and (box_width < width) and (box_depth < depth):
#             frappe.throw("%s can not be fitted in selected Box"%doc.item_code)
#         elif box_weight < weight:
#             frappe.throw("Item weight is greater than Box weight Limit")
#     else:
#         doc.box = ""

def validate_dimensions(doc):
    weight = doc.weight_
    if weight < 0:
        frappe.throw("Item's weight cannot be negative.")

    for item in doc.uoms:
        height = item.height
        width = item.width
        depth = item.length

        if (height < 0) or (width < 0) or (depth < 0):
            frappe.throw("Item's Dimension details cannot be negative.")

        # check the items Dimensions and box Dimensions
        if doc.unique_box_for_packing:
            box = frappe.get_doc("Item", doc.box)
            box_height = box.height
            box_width = box.width
            box_depth = box.length
            box_weight = box.weight_

            if (box_height < height) and (box_width < width) and (box_depth < depth):
                frappe.throw("%s can not be fitted in selected Box"%doc.item_code)
            elif box_weight < weight:
                frappe.throw("Item weight is greater than Box weight Limit")
        else:
            doc.box = ""