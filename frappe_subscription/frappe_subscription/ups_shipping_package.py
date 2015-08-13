import frappe
from lxml import etree
from lxml.builder import E
from frappe.utils import flt
from ups.shipping_package import ShipmentConfirm, ShipmentAccept
from frappe_subscription.frappe_subscription.ups_helper import UPSHelper as Helper

@frappe.whitelist()
def get_shipping_labels(delivery_note):
    # get package information from delivery note
    # create xml request for ups shipping_package
    # parse the xml response and store the shipping labels and tracking_id

    dn = frappe.get_doc("Delivery Note",delivery_note)

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
    package_type = params.get("package_type")
    ship_to_params = {
        "customer":dn.customer,
        "contact_display":dn.contact_display,
        "contact_mobile":dn.contact_mobile
    }

    packages = Helper.get_packages(packing_slips, "02")

    request = ShipmentConfirm.shipment_confirm_request_type(
        Helper.get_shipper(params),
        Helper.get_ship_to_address(ship_to_params, dn.shipping_address_name,),
        Helper.get_ship_from_address(params, ship_from_address_name),
        Helper.get_payment_info(AccountNumber=shipper_number),
        ShipmentConfirm.service_type(Code='03'),    # UPS Standard
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

            c = 1
            for package in shipment_result.iterchildren(tag='PackageResults'):
                tracking_id = package.find("TrackingNumber").text
                label = package.find("LabelImage").find("GraphicImage").text
                info.update({
                    c:{
                        "tracking_id":tracking_id,
                        "label":label
                    }
                })
                c+=1
        else:
            frappe.throw("Can Not find the Service and Total Charges Attribute in RatedShipment")

        return info
    else:
        frappe.throw(response.find("Response").find("ResponseStatusDescription").text)

def save_tracking_number_and_shipping_labels(dn, shipment_info):
    for row in dn.packing_slip_details:
        info = shipment_info.get(row.idx)
        if info:
            row.tracking_id = info.get("tracking_id")
            row.shipping_label = "<img src='data:image/gif;base64,%s'"%(info.get('label'))
            row.tracking_status = "Shipment Label(s) Created"
        else:
            frappe.throw("Error while parsing xml response")

    dn.dn_status = "Shipping Labels Created"
    dn.save(ignore_permissions=True)
