import frappe

def validate(doc, method):
    validate_uom_conversions(doc)
    validate_dimensions(doc)

def validate_uom_conversions(doc):
    count = 0
    count = sum(map(lambda item: item.default_shipping_uom or 0, doc.custom_uoms))
    if not count:
        frappe.throw("Please first select the default Custom                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    UOM Conversion Details")

    if doc.item_group == "Boxes" and "Nos" not in map(lambda item: item.uom, doc.custom_uoms):
        frappe.throw("Boxes should always have the Nos UOM")


# def validate_dimensions(doc):
#     height = doc.height
#     width = doc.width
#     depth = doc.length
#     weight = doc.weight_

#     if (height < 0) or (width < 0) or (depth < 0) or (weight < 0): 
#             frappe.throw("Item's Dimension details cannot be negative.")

#     # check the items Dimensions and box Dimensions

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
    box = None
    box_uoms = None


    if weight < 0:
        frappe.throw("Item's weight cannot be negative.")

    if doc.unique_box_for_packing:
        box = frappe.get_doc("Item", doc.box)
        box_uoms = box.custom_uoms

        if box_weight < weight:
            frappe.throw("Item weight is greater than Box weight Limit")

    for item in doc.custom_uoms:
        height = item.height
        width = item.width
        depth = item.length

        if (height < 0) or (width < 0) or (depth < 0):
            frappe.throw("Item's Dimension details cannot be negative.")

        # check the items Dimensions and box Dimensions
        if doc.unique_box_for_packing:
            box_height = box.height
            box_width = box.width
            box_depth = box.length
            box_weight = box.weight_

            if (box_height < height) and (box_width < width) and (box_depth < depth):
                frappe.throw("%s can not be fitted in selected Box if we use %s UOM"%(doc.item_code, item.uom))

        elif doc.box != "":
            doc.box = ""

@frappe.whitelist()
def get_default_uom(item_code):
    return frappe.db.get_value("Custom UOM Conversion Details", 
        {"parent":item_code, "default_shipping_uom":1}, ["uom", "conversion_factor"], as_dict=True)

@frappe.whitelist()
def get_conversion_factor(item_code, uom):
    return frappe.db.get_value("Custom UOM Conversion Details", 
        { "parent":item_code, "uom": uom }, "conversion_factor", as_dict=True)

def custom_uom_query(doctype, txt, searchfield, start, page_len, filters):
    item_code = filters.get("item_code")
    
    return frappe.db.sql('''select uom from `tabCustom UOM Conversion Details` 
                where parent="{}"'''.format(item_code))