import frappe
import json
from lxml import etree
from lxml.builder import E
from frappe.utils import flt
from ups.base import PyUPSException
from ups.shipping_package import ShipmentConfirm, ShipmentAccept
# from frappe_subscription.frappe_subscription.tasks import create_scheduler_log
from frappe_subscription.frappe_subscription.ups_helper import UPSHelper as Helper
from frappe_subscription.frappe_subscription.ups_mapper import ups_packages, ups_services

@frappe.whitelist()
def get_shipping_labels(delivery_note):
    # get package information from delivery note
    # create xml request for ups shipping_package
    # parse the xml response and store the shipping labels and tracking_id

    # dn = frappe.get_doc("Delivery Note",delivery_note)
    try:
        dn = delivery_note

        params = Helper.get_ups_api_params()
        shipment_confirm_api = get_shipment_confirm_service(params)
        shipment_accept_api = get_shipment_accept_service(params)
        shipment_confirm_request = get_ups_shipment_confirm_request(dn, params)

        response = shipment_confirm_api.request(shipment_confirm_request)
        digest = shipment_confirm_api.extract_digest(response)
        shipment_accept_request = ShipmentAccept.shipment_accept_request_type(digest)
        response = shipment_accept_api.request(shipment_accept_request)

        shipping_info = parse_xml_response_to_json(response, dn)

        # save tracking no and labels to delivery note
        save_tracking_number_and_shipping_labels(dn, shipping_info)
        # reduce box items from stock ledger
        dn.boxes_stock_entry = create_boxes_stock_entry(dn)
    except PyUPSException, e:
        frappe.throw(e[0])
    except Exception, e:
        import traceback
        print traceback.format_exc()
        frappe.throw("Can not reach to UPS Server please try after some time ...")

def get_shipment_confirm_service(params):
    return ShipmentConfirm(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        params.get("ups_mode"),         # sandbox for testing purpose set as True for production set it to False
    )

def get_shipment_accept_service(params):
    return ShipmentAccept(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        params.get("ups_mode"),         # sandbox for testing purpose set as True for production set it to False
    )

def get_ups_shipment_confirm_request(delivery_note, params):
    dn = delivery_note
    packing_slips = [row.packing_slip for row in dn.packing_slip_details]
    if not packing_slips:
        frappe.throw("Can not find the linked Packing Slip ...")

    ship_from_address_name = params.get("default_warehouse")
    shipper_number = params.get("shipper_number")
    package_type = ups_packages.get(params.get("package_type"))
    rates = {}
    if dn.ups_rates:
        rates = json.loads(dn.ups_rates)
    service_code = rates.get("service_used") or "03"
    ship_to_params = {
        "customer":dn.customer,
        "contact_display":dn.contact_display,
        "contact_mobile":dn.contact_mobile
    }

    packages = Helper.get_packages(packing_slips, package_type)

    request = ShipmentConfirm.shipment_confirm_request_type(
        Helper.get_shipper(params),
        Helper.get_ship_to_address(ship_to_params, dn.shipping_address_name,),
        Helper.get_ship_from_address(params, ship_from_address_name),
        Helper.get_payment_info(AccountNumber=shipper_number),
        ShipmentConfirm.service_type(Code=service_code),
        # TODO add label containers
        LabelSpecification = E.LabelSpecification(
            E.LabelPrintMethod(E.Code("ZPL"),),
            E.LabelStockSize(E.Height("4"),E.Width("6"),),
            E.LabelImageFormat(E.Code("ZPL"),),
        ),
        Description="Description"
    )
    request.find("Shipment").extend(packages)

    return request

def parse_xml_response_to_json(response, delivery_note):
    info = {}
    shipping_rate = flt(delivery_note.carrier_shipping_rate) or 0

    if response.find("Response").find("ResponseStatusCode").text == "1":
        shipment_result = response.find("ShipmentResults")
        shipment_charges = shipment_result.find("ShipmentCharges")
        total_charges = shipment_charges.find("TotalCharges")

        if shipment_result and total_charges:
            service_charges = total_charges.find("MonetaryValue")
            info.update({
                "total_charges": service_charges.text
            })

            # # check if Total Charges from ups and UPS rates are equal or not ?
            if flt(service_charges.text) == shipping_rate:
                package_details = set_packages_details(shipment_result)
                info.update(package_details)
            else:
                # set up the corrected shipping charges
                delivery_note.carrier_shipping_rate = flt(service_charges.text) or 0
                delivery_note.total_shipping_rate = delivery_note.carrier_shipping_rate or 0 + (delivery_note.carrier_shipping_rate or 0 * (delivery_note.shipping_overhead_rate or 0/100))

                from frappe_subscription.frappe_subscription.ec_delivery_note import get_shipping_overhead_row
                row = get_shipping_overhead_row(delivery_note)
                row.tax_amount = delivery_note.total_shipping_rate

                delivery_note.save(ignore_permissions=True)
                package_details = set_packages_details(shipment_result)
                info.update(package_details)
        else:
            frappe.throw("Can Not find the Service and Total Charges Attribute in RatedShipment")

        return info
    else:
        frappe.throw(response.find("Response").find("ResponseStatusDescription").text)

def set_packages_details(shipment_result):
    info = {}
    idx = 1
    for package in shipment_result.iterchildren(tag='PackageResults'):
        tracking_id = package.find("TrackingNumber").text
        label = package.find("LabelImage").find("GraphicImage").text
        # packing_slip = package.find("Description").text
        # packing_slip = packing_slip.split("/")[1]
        info.update({
            # packing_slip:{
            idx:{
                "tracking_id":tracking_id,
                "label":label
            }
        })
        idx += 1

    return info

# base64 bWFrYXJhbmQ=
# def save_shipping_labels_to_file(dn, base64_label, tracking_id, public_path):
def save_shipping_labels_to_file(dn, base64_label, tracking_id):
    base_path = check_and_get_base_path();
    zpl_label = base64_label.decode("base64")

    zpl_file = "%s/zpl/%s-%s.zpl"%(base_path, dn, tracking_id)

    with open(zpl_file, "w") as label:
        label.write(zpl_label)

    return zpl_to_png(zpl_file, dn, tracking_id, base_path);

def zpl_to_png(zpl_path, dn, tracking_id, base_path):
    import os
    api_path = "http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/"
    png_path = "%s/png/%s-%s.png"%(base_path, dn, tracking_id)
    filename = "%s-%s.png"%(dn, tracking_id)

    os.system("curl --request POST %s --form file=@%s > %s"%(api_path, zpl_path, png_path))

    set_aspect_ratio(png_path)

    return filename

def set_aspect_ratio(img_path):
    import PIL
    from PIL import Image
    #size in pixel
    basewidth = 384
    img = Image.open(img_path)
    wpercent = (basewidth/float(img.size[0]))
    hsize = int((float(img.size[1])*float(wpercent)))
    img = img.resize((basewidth,hsize), PIL.Image.ANTIALIAS)
    img.save(img_path)

def check_and_get_base_path():
    import os

    public_path = os.path.join(frappe.local.site_path, "public","files")
    cwd = "%s/%s"%(os.getcwd(),public_path.split("./")[1])
    dir_path = "%s/labels"%(cwd)

    # labels dir doesn't exsit, so create new dir
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
        os.mkdir("%s/zpl"%(dir_path))
        os.mkdir("%s/png"%(dir_path))
    else:
        zpl_path = "%s/zpl"%dir_path
        png_path = "%s/png"%dir_path

        if not os.path.isdir(zpl_path):
            os.mkdir(zpl_path)
        elif not os.path.isdir(png_path):
            os.mkdir(png_path)

    return dir_path

def save_tracking_number_and_shipping_labels(dn, shipment_info):
    for row in dn.packing_slip_details:
        info = shipment_info.get(row.idx)
        if info:
            row.tracking_id = info.get("tracking_id")
            # row.shipping_label = "<img src='data:image/gif;base64,%s' class='ups-label'/>"%(info.get('label'))
            # TODO configure path
            row.label_path = save_shipping_labels_to_file(
                                dn.name,
                                info.get('label'),
                                info.get("tracking_id")
                            )
            row.tracking_status = "Labels Printed"

            update_packing_slip(row.packing_slip, info)
        else:
            frappe.throw("Error while parsing xml response")

    dn.dn_status = "Shipping Labels Created"
    # dn.save(ignore_permissions=True)

def update_packing_slip(packing_slip, info):
    query = """UPDATE `tabPacking Slip` SET tracking_id='%s', tracking_status='%s',
            track_status='Auto' WHERE name='%s'"""%(info.get("tracking_id"),
            "Labels Printed", packing_slip)
    frappe.db.sql(query)

def create_boxes_stock_entry(delivery_note):
    from datetime import datetime as dt
    from frappe.utils.dateutils import datetime_in_user_format, get_user_date_format, dateformats

    doc = delivery_note
    boxes_used = {}
    for row in doc.packing_slip_details:
        qty = (boxes_used.get(row.item_code) + 1) if boxes_used.get(row.item_code) else 1

        warehouse = frappe.db.get_value("Item", row.item_code, "default_warehouse")
        available_qty = frappe.db.get_value("Bin",{"item_code":row.item_code, "warehouse":warehouse},"actual_qty") or 0
        if available_qty < qty:
            frappe.throw("Please check the stock balance for Box : %s"%row.item_code)
        boxes_used.update({
            row.item_code:qty
        })
    se = frappe.new_doc("Stock Entry")
    se.posting_date = dt.now().strftime("%Y-%m-%d")
    # se.posting_date = dt.strptime(datetime_in_user_format(dt.now()), dateformats[get_user_date_format()])

    se.posting_time = dt.now().strftime("%H:%M:%S")
    se.purpose = "Material Issue"
    se.from_warehouse = "EC Home - EC"
    se.set("items",[])

    for item, qty in boxes_used.iteritems():
        ch = se.append("items",{})
        ret = frappe._dict(se.get_item_details(args={"item_code":item}))
        ch.item_code = item
        ch.item_name = ret.item_name
        ch.qty = qty
        ch.uom = ret.uom
        ch.stock_uom = ret.stock_uom
        ch.description = ret.description
        ch.image = ch.image
        ch.expense_account = ret.expense_account
        ch.cost_center = ret.cost_center
        ch.conversion_factor = ret.conversion_factor
        ch.transfer_qty = ret.transfer_qty
        ch.batch_no = ret.batch_no
        ch.actual_qty = ret.actual_qty
        ch.incoming_rate = ret.incoming_rate

    se.submit()
    return se.name
