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

        shipping_info = parse_xml_response_to_json(response)

        # save tracking no and labels to delivery note
        save_tracking_number_and_shipping_labels(dn, shipping_info)
        # reduce box items from stock ledger
        dn.boxes_stock_entry = create_boxes_stock_entry(dn)
    except PyUPSException, e:
        frappe.throw(e[0])

def get_shipment_confirm_service(params):
    return ShipmentConfirm(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        True                        # sandbox for testing purpose set as True for production set it to False
    )

def get_shipment_accept_service(params):
    return ShipmentAccept(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        True                        # sandbox for testing purpose set as True for production set it to False
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
        # ShipmentConfirm.service_type(Code='03'),    # UPS Standard #TODO add service_type
        ShipmentConfirm.service_type(Code=service_code),
        Description="Description"
    )
    request.find("Shipment").extend(packages)
    return request

def parse_xml_response_to_json(response):
    info = {}
    if response.find("Response").find("ResponseStatusCode").text == "1":
        shipment_result = response.find("ShipmentResults")
        shipment_charges = shipment_result.find("ShipmentCharges")
        total_charges = shipment_charges.find("TotalCharges")

        if shipment_result and total_charges:
            service_charges = total_charges.find("MonetaryValue")
            info.update({
                "total_charges": service_charges.text
            })

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
        else:
            frappe.throw("Can Not find the Service and Total Charges Attribute in RatedShipment")

        return info
    else:
        frappe.throw(response.find("Response").find("ResponseStatusDescription").text)

def save_tracking_number_and_shipping_labels(dn, shipment_info):
    for row in dn.packing_slip_details:
        # info = shipment_info.get(row.packing_slip)
        info = shipment_info.get(row.idx)
        if info:
            row.tracking_id = info.get("tracking_id")
            row.shipping_label = "<img src='data:image/gif;base64,%s'/>"%(info.get('label'))
            row.tracking_status = "Labels Printed"

            query = """Update `tabPacking Slip` set tracking_id='%s' where
                    delivery_note='%s' and name='%s'"""%(info.get("tracking_id"),
                    dn.name, row.packing_slip)
            frappe.db.sql(query)
        else:
            frappe.throw("Error while parsing xml response")

        update_packing_slip(row.packing_slip, info)

    dn.dn_status = "Shipping Labels Created"
    # dn.save(ignore_permissions=True)

def update_packing_slip(packing_slip, info):
    query = """UPDATE `tabPacking Slip` set tracking_id='%s', tracking_status='%s'
            WHERE name='%s'"""%(info.get("tracking_id"), "Labels Printed",
            packing_slip)
    frappe.db.sql(query)

def create_boxes_stock_entry(delivery_note):
    from datetime import datetime as dt
    from frappe.utils.dateutils import datetime_in_user_format, get_user_date_format, dateformats

    doc = delivery_note
    boxes_used = {}
    for row in doc.packing_slip_details:
        qty = (boxes_used.get(row.item_code) + 1) if boxes_used.get(row.item_code) else 1

        warehouse = frappe.db.get_value("Item", row.item_code, "default_warehouse")
        available_qty = frappe.db.get_value("Bin",{"item_code":"row.item_code", "warehouse":warehouse},"actual_qty") or 0
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
