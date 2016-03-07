import frappe
from frappe.utils import flt

def validate(doc, method):
    # TODO unique box reqd and uom is box ?
    validate_uom_conversions(doc)
    validate_dimensions(doc)
    if all([True for item in doc.custom_uoms if item.uom == "Box"] or [False]):
        validate_item_packing_qty(doc)

def validate_uom_conversions(doc):
    if not all(map(lambda item: item.conversion_factor > 0, doc.custom_uoms)):
        frappe.throw("Conversion factor can not be negative")

    count = 0
    count = sum(map(lambda item: item.default_shipping_uom or 0, doc.custom_uoms))
    if count == 0 and len(doc.custom_uoms) > 1:
        frappe.throw("Please first select the default Custom UOM Conversion Details")
    elif count == 0 and len(doc.custom_uoms) == 1:
        doc.custom_uoms[0].default_shipping_uom = 1

    uom_list = map(lambda item: item.uom, doc.custom_uoms)
    if doc.item_group == "Boxes" and "Nos" not in uom_list:
        frappe.throw("Boxes should always have the Nos UOM")
    elif doc.item_group == "Boxes" and "Box" in uom_list:
        frappe.throw("Box Item can have Box UOM")

def validate_dimensions(doc):
    box = None
    box_uoms = None
    box_height = 0
    box_width = 0
    box_depth = 0

    if doc.unique_box_for_packing:
        # get box's dimensions as item dimension
        box = frappe.db.get_value("Custom UOM Conversion Details", {
                    "parent": doc.box,
                    "uom": "Nos"
                }, ["height", "weight", "width", "length", "conversion_factor"], as_dict=True)
        if box:
            box_weight = box.get("weight")
            box_height = box.get("height")
            box_width = box.get("width")
            box_depth = box.get("length")
        else:
            frappe.throw("Invalid dimensions for {}".format(doc.box))
    else:
        box = [box for box in doc.custom_uoms if box.uom=="Box"] or None
        if box and box[0]:
            box_weight = box[0].weight
            box_height = box[0].height
            box_width = box[0].width
            box_depth = box[0].length

    for item in doc.custom_uoms:
        height = item.height
        width = item.width
        depth = item.length
        weight = item.weight

        if any([height < 0, width < 0, depth < 0, weight < 0]):
            frappe.throw("Item's Dimension details cannot be negative.")

        if item.uom == "Nos" and box:
            if any([box_height < height, box_width < width, box_depth < depth, box_weight < weight]):
                frappe.throw("%s can not be fitted in selected Box if we use %s UOM"%(doc.item_code, item.uom))
            elif item.conversion_factor != 1:
                frappe.throw("Conversion factor should be 1 for Nos UOM")
        elif item.uom == "Box" and box:
            if any([box_height > height, box_width > width, box_depth > depth, box_weight > weight]):
                frappe.throw("Dimensions for the %s UOM should be greater than the %s's Dimensions"%(item.uom, doc.box))
            elif item.conversion_factor <= 0:
                frappe.throw("Invalide Conversion factor for Box")

def validate_item_packing_qty(doc):
    # check if number of items (qty > conversion factor) fits in Box dimentions

    from frappe_subscription.bin_packing import (params, get_bin_packing_credentials,
                get_bin_packing_request, get_bin_packing_response)

    bins = {}
    bin_dimension = ""
    bin_weight = 0
    items = {}
    item_dimension = ""
    item_weight = 0
    qty = 0
    box = None

    if doc.unique_box_for_packing:
        # get box's dimensions as item dimension
        box = frappe.db.get_value("Custom UOM Conversion Details", {
                    "parent": doc.box,
                    "uom": "Nos"
                }, ["height", "weight", "width", "length", "conversion_factor"], as_dict=True)
        if not box:
            frappe.throw("Invalid dimensions for {}".format(doc.box))

    for item in doc.custom_uoms:
        if item.uom == "Nos":
            if doc.unique_box_for_packing:
                height = box.get("height")
                weight = box.get("weight")
                length = box.get("length")
                width = box.get("width")
            else:
                height = item.height
                weight = item.weight
                length = item.length
                width = item.width    

            if height and width and length and weight:
                items = {
                    "id":doc.item_code, "h":height,
                    "w":width, "d":length,
                    "wg":weight
                }
                item_dimension = "{} x {} x {}".format(flt(width, 2), flt(height, 2), flt(length, 2))
                item_weight = flt(weight, 2)
            else:
                frappe.throw("Please set the valid dimension details for Nos UOM")
        elif item.uom == "Box":
            qty = item.conversion_factor
            box_uom = item
            if item.height and item.width and item.length and item.weight:
                bins = {
                    "id":"%s-box"%doc.item_code, "h":item.height,
                    "w":item.width, "d":item.length,
                    "max_wg":item.weight
                }
                bin_dimension = "{} x {} x {}".format(flt(item.width, 2), flt(item.height, 2), flt(item.length, 2))
                bin_weight = flt(item.weight, 2)
            else:
                frappe.throw("Please set the valid dimension details for Nos UOM")

    if all([item, bins, qty]):
        items.update({ "q": qty })
        credentials = get_bin_packing_credentials()
        request = get_bin_packing_request([bins],[items],credentials,params)
        response = get_bin_packing_response(request, api_xpath="/packer/pack")
        stat = get_bin_packing_stat(response.get("response"), bin_dimension, bin_weight, item_dimension, item_weight) or {}
        box_uom.conversion_factor = stat.get("qty_packed") or 0
        box_uom.bin_stat = stat.get("html") or ""
    else:
        frappe.throw("Error occured while checking packing information, Please contact Administrator")
    
def get_bin_packing_stat(response, box_dimensions, box_weight, item_dimensions, item_weight):
    qty_not_packed = 0
    space_used = 0
    weight_used = 0
    qty_packed = 0
    
    packed_bin = response.get("bins_packed")[0] if response.get("bins_packed") else None
    if not packed_bin:
        frappe.throw("Bin Packing Information not available in response")
    
    not_packed_items = packed_bin.get("not_packed_items")
    bin_data = packed_bin.get("bin_data")

    if not_packed_items:
        qty_not_packed = not_packed_items[0].get("q") or 0


    qty_packed = len(packed_bin.get("items")) or 0
    space_used = bin_data.get("used_space")
    weight_used = bin_data.get("used_weight")
    html = frappe.render_template("templates/pages/bin_packing_stat.html",{
                "qty_packed": qty_packed,
                "qty_not_packed": qty_not_packed,
                "space_used": space_used,
                "weight_used": weight_used,
                "img": packed_bin.get("image_complete"),
                "box_dimensions": box_dimensions,
                "box_weight": box_weight,
                "item_dimensions": item_dimensions,
                "item_weight": item_weight,
            }, is_path=True)

    return {
        "qty_packed": qty_packed,
        "html": html
    }

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
