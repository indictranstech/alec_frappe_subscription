import frappe

def validate(doc, method):
    # TODO unique box reqd and uom is box ?
    validate_uom_conversions(doc)
    validate_dimensions(doc)
    default_uom = [item.uom for item in doc.custom_uoms if item.default_shipping_uom]
    if default_uom and default_uom[0] == "Box":
        # check if number of items (qty > conversion factor) fits in Box dimentions
        validate_item_packing_qty(doc)


def validate_uom_conversions(doc):
    count = 0
    count = sum(map(lambda item: item.default_shipping_uom or 0, doc.custom_uoms))
    if not count:
        frappe.throw("Please first select the default Custom                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    UOM Conversion Details")

    if doc.item_group == "Boxes" and "Nos" not in map(lambda item: item.uom, doc.custom_uoms):
        frappe.throw("Boxes should always have the Nos UOM")

def validate_dimensions(doc):
    weight = doc.weight_
    box = None
    box_uoms = None
    box_height = 0
    box_width = 0
    box_depth = 0


    if weight < 0:
        frappe.throw("Item's weight cannot be negative.")

    if doc.unique_box_for_packing:
        box = frappe.get_doc("Item", doc.box)
        box_uoms = box.custom_uoms

        if box.weight_ < weight:
            frappe.throw("Item weight is greater than Box weight Limit")

        for rec in box_uoms:
            if rec.uom == "Nos":
                box_height = rec.height
                box_width = rec.width
                box_depth = rec.length

    for item in doc.custom_uoms:
        height = item.height
        width = item.width
        depth = item.length

        if (height < 0) or (width < 0) or (depth < 0):
            frappe.throw("Item's Dimension details cannot be negative.")

        # check the items Dimensions and box Dimensions
        if doc.unique_box_for_packing:
            if (box_height < height) and (box_width < width) and (box_depth < depth):
                frappe.throw("%s can not be fitted in selected Box if we use %s UOM"%(doc.item_code, item.uom))

        elif doc.box != "":
            doc.box = ""

def validate_item_packing_qty(doc):
    from frappe_subscription.bin_packing import params, get_bin_packing_credentials, get_bin_packing_request, get_bin_packing_response

    bins = {}
    items = {}
    qty = 0
    cdn = None

    for item in doc.custom_uoms:
        if item.uom == "Nos":
            if item.height and item.width and item.length and item.weight:
                items = {
                    "id":doc.item_code, "h":item.height,
                    "w":item.width, "d":item.length,
                    "wg":item.weight
                }
            else:
                frappe.throw("Please set the valid dimension details for Nos UOM")
        elif item.uom == "Box":
            qty = item.conversion_factor
            cdn = item.name
            box_uom = item
            if item.height and item.width and item.length and item.weight:
                bins = {
                    "id":"%s-box"%doc.item_code, "h":item.height,
                    "w":item.width, "d":item.length,
                    "max_wg":item.weight
                }
            else:
                frappe.throw("Please set the valid dimension details for Nos UOM")

    if all([item, bins, qty, cdn]):
        items.update({ "q": qty })
        credentials = get_bin_packing_credentials()
        request = get_bin_packing_request([bins],[items],credentials,params)
        response = get_bin_packing_response(request, api_xpath="/packer/pack")
        stat = get_bin_packing_stat(response.get("response")) or {}
        box_uom.conversion_factor = stat.get("qty_packed") or 0
        box_uom.bin_stat = stat.get("html") or ""
        # frappe.db.set_value("Custom UOM Conversion Details", cdn, "bin_stat", )
    else:
        frappe.errprint("Error occured while checking packing information, Please contact Administrator")
    
def get_bin_packing_stat(response):
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
    # html = prepare_bin_stat_html(qty_not_packed=qty_not_packed, qty_packed=qty_packed, 
    #     weight_used=weight_used, space_used=space_used, img=packed_bin.get("image_complete"))
    html = frappe.render_template("templates/pages/bin_packing_stat.html",{
                "qty_packed": qty_packed,
                "qty_not_packed": qty_not_packed,
                "space_used": space_used,
                "weight_used": weight_used,
                "img": packed_bin.get("image_complete")
            }, is_path=True)

    frappe.errprint(html)
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