import frappe
import httplib
import urllib
import json

from ec_packing_slip import get_packing_slip_details

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

def get_bin_packing_details(delivery_note, items):
    # check item group of item
    items_to_pack = []
    for item in items:
        item_details = frappe.db.get_values("Item",item.item_code,
                                            ["item_group", "unique_box_for_packing", "height", "width", "length", "weight_"],
                                            as_dict=True)
        if not item_details:
            frappe.throw("Invalid Item")
        else:
            item_group = item_details[0].get("item_group")
            uses_unique_packing_box = item_details[0].get("unique_box_for_packing") or 0
            if (item_group != "Boxes") and (not uses_unique_packing_box):
                height = item_details[0].get("height") or 0
                width = item_details[0].get("width") or 0
                depth = item_details[0].get("length") or 0
                weight = item_details[0].get("weight_") or 0

                if height and width and depth and weight:
                    # valid item continue with further processing
                    to_dict = {
                        "w": width, "h": height,
                        "d": depth, "q": item.qty,
                        "vr": 1, "id": item.item_code,
                        "wg": weight
                    }
                    items_to_pack.append(to_dict)
                else:
                    frappe.throw("Please set the valid dimension details for {0}-{1} item".format(item.item_code, item.item_name))

    if items_to_pack:
        # prepare 3d bin packing request in json format
        bins = get_bin_details()
        credentials = get_bin_packing_credentials()
        request = get_bin_packing_request(bins,items_to_pack,credentials,params)
        response = get_bin_packing_response(request)
        return get_packing_slip_details(delivery_note, response.get("response"))
    else:
        frappe.throw("No items found for bin packing process")

def get_bin_details():
    # get item with item group boxes
    # exclude the unique packing boxes
    bins = []

    query = """SELECT
                i.name, i.width, i.height, i.length, i.weight_
            FROM
                `tabItem` i,
                `tabBin` b
            WHERE
                i.item_group='Boxes'
            AND i.name NOT IN (SELECT box FROM `tabItem` WHERE unique_box_for_packing=1)
            AND b.item_code=i.item_code
            AND b.actual_qty>0"""

    items = frappe.db.sql(query,as_dict=True)

    for item in items:
        height = item.get('height')
        width = item.get("width")
        depth = item.get("length")
        weight = item.get("weight_")

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

def get_bin_packing_response(request):
    connection = httplib.HTTPConnection(host='eu.api.3dbinpacking.com', port=80)
    req_params =  urllib.urlencode({'query':json.dumps(request)})
    headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
    connection.request("POST", "/packer/packIntoMany", req_params, headers)
    content = connection.getresponse().read()
    connection.close()

    response = json.loads(content)
    if response.get("response").get("status") == 1:
        return response
    else:
        frappe.throw("Error !!")
