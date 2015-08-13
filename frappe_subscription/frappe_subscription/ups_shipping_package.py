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
    frappe.errprint(etree.tostring(response, pretty_print=True))
    s
    response = rating_api.request(request)
    shipping_rates = parse_xml_response_to_json(response)

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
