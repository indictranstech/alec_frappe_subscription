import json
import frappe
import httplib
import urllib
from ec_packing_slip import get_packing_slip_details

# parameter required for 3D bin packing API
params = {
    "images_background_color": "255,255,255",
    "images_bin_border_color": "59,59,59",
    "images_bin_fill_color": "230,230,230",
    "images_item_border_color": "214,79,79",
    "images_item_fill_color": "177,14,14",
    "images_item_back_border_color": "215,103,103",
    "images_sbs_last_item_fill_color": "99,93,93",
    "images_sbs_last_item_border_color": "145,133,133",
    "images_width": "100",
    "images_height": "100",
    "images_source": "base64",
    "images_sbs": "1",
    "stats": "1",
    "item_coordinates": "1",
    "images_complete": "1",
    "images_separated": "1"
}

@frappe.whitelist()
def get_bin_packing_details(delivery_note):
        """create 3D bin packing API JSON request and parse the JSON response"""
#    try:
        # dn = frappe.get_doc("Delivery Note", delivery_note)
        dn = frappe.get_doc(json.loads(delivery_note))
        delete_ps = []

        if dn.dn_status not in ["Draft","Partialy Packed", "Manual Partialy Packed", "Manual Packing Slips Created"]:
            frappe.throw("Packing Slips are already created. Please Reload the Document")
        else:
            if dn.dn_status in ["Draft", "Manual Partialy Packed", "Manual Packing Slips Created"]:
                if dn.packing_slip_details:
                    for ps in dn.packing_slip_details:
                        if ps.packing_slip :
                            delete_ps.append(ps)
                if delete_ps:
                    for chlid_row in delete_ps:
                        if chlid_row.packing_slip:
                            frappe.errprint(chlid_row.packing_slip)
                            frappe.db.sql("""update `tabPacking Slip` set docstatus = 2 where name = '%s' """%(chlid_row.packing_slip))
                            frappe.delete_doc("Packing Slip", chlid_row.packing_slip, force=True, ignore_permissions=True)
                        dn.remove(chlid_row)

            items_to_pack = get_items_to_pack(dn)
            to_pack = [item.get("id") for item in items_to_pack]

            # get unique box items to create packing slips
            items_with_unique_boxes = get_unique_box_items_to_pack(dn, to_pack)

            if items_to_pack:
                bins = get_bin_details()
                if not bins:
                    frappe.throw("No Bins Founds, Please check the stock")
                credentials = get_bin_packing_credentials()
                request = get_bin_packing_request(bins,items_to_pack,credentials,params)
                response = get_bin_packing_response(request)
                return get_packing_slip_details(delivery_note, response.get("response"), items_with_unique_boxes)
            elif items_with_unique_boxes:
                return get_packing_slip_details(delivery_note, None, items_with_unique_boxes)
            else:
                frappe.throw("No items found for bin packing process")

        dn.pack_manualy = 0
        dn.save(ignore_permissions = True)
        
        return "Packing Slips"
 #   except Exception, e:
 #       frappe.throw(e)

def get_items_to_pack(dn):
    """Get the delivery note items, if dn_status is Draft else get the items from not_packed_items field"""
    items_to_pack = []

    # if dn.dn_status == "Draft":
    if dn.dn_status in ["Draft", "Manual Partialy Packed", "Manual Packing Slips Created"]:
        items = dn.items
        for item in dn.items:
            to_dict = get_item_details(item.item_code, item.custom_qty, custom_uom=item.custom_uom, dn=dn.name)
            if item.custom_qty > 0:
                if to_dict:
                    items_to_pack.extend(to_dict) if isinstance(to_dict, list) else items_to_pack.append(to_dict)
            else:
                frappe.throw("%s Item Qty must be greater than 0"%(item.item_code))
    elif dn.dn_status == "Partialy Packed":
        items = json.loads(dn.not_packed_items)
        for item_code, qty in items.iteritems():
            to_dict = get_item_details(item_code, qty, dn=dn.name)
            if qty > 0:
                if to_dict:
                    items_to_pack.extend(to_dict) if isinstance(to_dict, list) else items_to_pack.append(to_dict)
            else:
                frappe.throw("%s Item Qty must be greater than 0"%(item.item_code))

    return items_to_pack

def get_item_details(item_code, qty, custom_uom=None, dn=None):
    """
    Get item details like height, depth, lenght, weight and return 3D bin API dict structure for item details
    {
        "w":item_width, "h":item_height,
        "d":item_depth, "q":qty,
        "vr":1, "id":item_code,
        "wg":weight
    }
    """
    if all([not custom_uom, not dn]):
        frappe.throw("Custom UOM and Delivery Note name not found")
    elif not custom_uom:
        # get custom uom
        custom_uom = frappe.db.get_value("Delivery Note Item", { "parent": dn, "item_code":item_code }, "custom_uom")

    item_details = frappe.db.get_values("Item",item_code, ["item_group", "unique_box_for_packing"], as_dict=True)
    if not item_details:
        frappe.throw("Invalid Item")
    else:
        item_details = item_details[0]
        item_group = item_details.get("item_group")
        uses_unique_packing_box = item_details.get("unique_box_for_packing") or 0

        dimensions = frappe.db.get_value("Custom UOM Conversion Details",
            {"parent":item_code, "uom":custom_uom}, ["height", "width", "length", "weight", "conversion_factor"], as_dict=True)

        if not dimensions:
            frappe.throw("Item dimensions not found in Cusomt UOM Conversion Details")

        if item_group == "Boxes":
            return None

        if uses_unique_packing_box and custom_uom == "Nos":
            return None
        else:
            height = dimensions.get("height") or 0
            width = dimensions.get("width") or 0
            depth = dimensions.get("length") or 0
            weight = dimensions.get("weight") if custom_uom == "Nos" else frappe.db.get_value("Custom UOM Conversion Details",
                {"parent":item_code, "uom":"Nos"}, "weight")
            if height and width and depth and weight:
                if custom_uom == "Nos":
                    to_dict = {
                        "w": width, "h": height,
                        "d": depth, "q": qty,
                        "vr": 1, "id": item_code,
                        "wg": weight
                    }
                elif custom_uom == "Box":
                    qty_mapping = frappe.db.get_value("Delivery Note Item", { "parent": dn, "item_code": item_code}, "qty_mapping")
                    to_dict = [{
                        "w": width, "h": height,
                        "d": depth, "q": 1,
                        "vr": 1, "id": item_code,
                        "wg": q * weight
                    } for k, q in json.loads(qty_mapping).iteritems()]
                return to_dict
            else:
                frappe.throw("Please set the valid dimension details for {0} item".format(item_code))

# TO CHECK
def get_unique_box_items_to_pack(dn, to_pack):
    """get items which uses the unique box for packing,  if dn_status is Draft else get the items from not_packed_items field"""
    items_with_unique_boxes = []
    # if dn.dn_status == "Draft":
    if dn.dn_status in ["Draft", "Manual Partialy Packed", "Manual Packing Slips Created"]:
        for item in dn.items:
            if item.item_code not in to_pack:
                # check if item requires unique Box
                if frappe.db.get_value("Item", item.item_code,"unique_box_for_packing") and item.custom_uom == "Nos":
                    item_details = get_item_with_unique_box_details(item.item_code, item.qty)
                    [items_with_unique_boxes.append(item_details) for i in xrange(int(item.qty))]
    elif dn.dn_status == "Partialy Packed":
        items = json.loads(dn.not_packed_items)
        for item_code, qty in items.iteritems():
            if frappe.db.get_value("Item", item_code,"unique_box_for_packing") and item.custom_uom == "Nos":
                item_details = get_item_with_unique_box_details(item_code, qty)
                [items_with_unique_boxes.append(item_details) for i in xrange(int(qty))]
    return items_with_unique_boxes

def get_item_with_unique_box_details(item_code, qty):
    """
        prepare 3D bin API like response for items with unique boxes
        {
            "bin_data": {
                "w": box_w,
                "h": box_h,
                "d": box_d,
                "id": "box_id",
                "used_space": 100,
                "weight": item_wt,
                "used_weight": 100
            },
            "items": [{
                "id": "item_code",
                "w": item_width,
                "h": item_height,
                "d": item_depth,
                "wg": item_weight,
                "image_sbs": "image of box containing 1 item",
            }]
        }
    """
    box_item_code = ""
    to_dict = {}

    # item_details = frappe.db.get_values("Item",item_code,
    #                                     ["item_group", "unique_box_for_packing", "height", "width", "length", "weight_","box"],
    #                                     as_dict=True)

    query = """ select i.item_group, i.unique_box_for_packing, i.box ,
                uom.height, uom.weight, uom.width, uom.length from tabItem i,
                `tabCustom UOM Conversion Details` uom where i.name ='{0}' and
                uom.default_shipping_uom=1 and uom.parent='{0}' """.format(item_code)

    item_details = frappe.db.sql(query, as_dict=1)

    if not item_details:
        frappe.throw("%s Item Details Not found"%(item_code))
    else:
        box_item_code = item_details[0].get("box")
        item_group = item_details[0].get("item_group")
        if (item_group != "Boxes"):
            height = item_details[0].get("height") or 0
            width = item_details[0].get("width") or 0
            depth = item_details[0].get("length") or 0
            weight = item_details[0].get("weight") or 0

            if height and width and depth and weight:
                # valid item continue with further processing
                to_dict.update({
                    "items":[{
                        "w": width, "h": height,
                        "d": depth, "id": item_code,
                        "wg": weight,
                        "image_sbs":"""iVBORw0KGgoAAAANSUhEUgAAAGYAAABlBAMAAABNZYv/AAAAG1BMVEX///87Ozvm5uaxDg7WT0/XZ2eRhYVjXV3IyMiQHr\
                                    0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABAUlEQVRYhe3YOxaDMAxEUVf0aVjfVLAD2D5/sOXC89ocu795dJGUUnjD2npT\
                                    JGlukWXhmbky7cwajZGpjJGJxslE42SCsTLBWJnSeJnSeJnCmJnCmJncuJncuJnM2JnM2JnP+JnP+JnXgMxrQOYxJPMYkr\
                                    kNytwGZS7DMpdhmdPAzGlg5jA0cxia2c0wtV780YV/2m7GbrrppptuuvlbI272v21sxM0xhVAjbs6hChpxc82IzIibe+RF\
                                    Rtw8Ezwx4uZdSIARN99+5Rtxk62LthE3+fbrGnFTLPOmETflbcIz4iacWiwjbuLlyDHipjqEGSZmDFPf9cbmblZl0q/5Kr\
                                    IBGDsbH0e414QAAAAASUVORK5CYII="""
                    }]
                })
            else:
                frappe.throw("Please set the valid dimension details for {0} item".format(item_code))

    # box_details = frappe.db.get_values("Item",box_item_code,
    #                                     ["item_group", "height", "width", "length", "weight_"],
    #                                     as_dict=True)

    query = """ select i.item_group, uom.height, uom.weight, uom.width, uom.length from tabItem i,
                `tabCustom UOM Conversion Details` uom where i.name ='{0}' and
                uom.default_shipping_uom=1 and uom.parent='{0}' """.format(box_item_code)

    box_details = frappe.db.sql(query, as_dict=1)
    
    if not box_details:
        frappe.throw("%s Box Item Details Not found"%(box_item_code))
    else:
        item_group = box_details[0].get("item_group")
        if (item_group == "Boxes"):
            height = box_details[0].get("height") or 0
            width = box_details[0].get("width") or 0
            depth = box_details[0].get("length") or 0
            weight = item_details[0].get("weight") or 0

            if height and width and depth and weight:
                # valid box continue with further processing
                to_dict.update({
                    "bin_data":{
                        "w": width, "h": height,
                        "d": depth, "q": qty,
                        "id": item_details[0].get("box"),
                        "used_space": 100, "weight": weight,
                        "used_weight": 100
                    }
                })
            else:
                frappe.throw("Please set the valid dimension details for {0} Box item".format(item_code))
    return to_dict

def get_bin_details():
    """get item with item group boxes, exclude the unique packing boxes"""

    bins = []
    query = """SELECT
                i.name, u.width, u.height, u.length, u.weight
            FROM
                `tabItem` i,
                `tabCustom UOM Conversion Details` u,
                `tabBin` b
            WHERE
                i.item_group='Boxes'
            AND i.name NOT IN (SELECT box FROM `tabItem` WHERE unique_box_for_packing=1)
            AND b.item_code=i.item_code
            AND b.warehouse=i.default_warehouse
            AND u.parent=i.item_code
            AND u.uom='Nos'
            AND b.actual_qty>0"""

    items = frappe.db.sql(query,as_dict=True,debug=1)

    for item in items:
        height = item.get('height')
        width = item.get("width")
        depth = item.get("length")
        weight = item.get("weight")

        if height and width and depth and weight:
            bins.append({
                "id":item.name, "h":height,
                "w":width, "d":depth,
                "max_wg":weight
            })
        else:
            frappe.throw("Please set the valid dimension details for {0} item".format(item.name))

    return bins

def get_bin_packing_credentials():
    config = frappe.db.get_values("Shipping Configuration","Shipping Configuration",["binpacking_user_name","binpacking_api_key"],
                                as_dict=True)
    if not config:
        frappe.throw("Error while retrieving 3D Bin Packing Credentials Please check Shipping Configuration document")
    else:
        if config[0].get("binpacking_user_name") and config[0].get("binpacking_api_key"):
            # got valid username and api key
            return {
                "username": config[0].get("binpacking_user_name"),
                "api_key": config[0].get("binpacking_api_key")
            }
        else:
            frappe.throw("Invalid User Name and API Key for 3D Bin Packing")

def get_bin_packing_request(bins, items, credentials, params):
    return {
        "bins": bins,
        "items": items,
        "username": credentials.get("username"),
        "api_key": credentials.get("api_key"),
        "params": params
    }

def get_bin_packing_response(request, api_xpath="/packer/packIntoMany"):
    connection = httplib.HTTPConnection(host='eu.api.3dbinpacking.com', port=80)
    req_params =  urllib.urlencode({'query':json.dumps(request)})
    headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
    # connection.request("POST", "/packer/packIntoMany", req_params, headers)
    connection.request("POST", api_xpath, req_params, headers)
    content = connection.getresponse().read()
    connection.close()

    response = json.loads(content)
    if response.get("response").get("status") == 1:
        return response
    else:
        errors = response.get("response").get("errors")
        # msg = "Packing Slip can not be created\n%s"%("\n".join(errors))
        msg = """3D Bin Packing Algorithm Error. If trying to add dimensions,
               be sure that Nos is already created. """
        frappe.throw(msg)
