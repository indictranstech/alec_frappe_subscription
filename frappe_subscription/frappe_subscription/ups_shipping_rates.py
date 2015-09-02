import frappe
import json
from lxml import etree
from lxml.builder import E

from frappe.utils import flt
from ups.base import PyUPSException
from ups.rating_package import RatingService
from frappe_subscription.frappe_subscription.ups_mapper import ups_packages
from frappe_subscription.frappe_subscription.ups_helper import UPSHelper as Helper

@frappe.whitelist()
def get_shipping_rates(delivery_note, add_shipping_overhead=False):
    # get packages Information from delivery note
    # create the xml request to fetch the ups rates
    try:
        dn = frappe.get_doc("Delivery Note",delivery_note)

        if dn.dn_status in ["Draft", "Partialy Packed"]:
            frappe.throw("First create the packing slips")

        params = Helper.get_ups_api_params()
        rating_api = get_rating_service(params)
        request = get_ups_rating_request(dn, params)

        response = rating_api.request(request)
        shipping_rates = parse_xml_response_to_json(response)

        dn.ups_rates = json.dumps(shipping_rates)
        dn.dn_status = "UPS Rates Fetched"

        dn.save(ignore_permissions= True)
        if shipping_rates.get("03"):
            if add_shipping_overhead: add_shipping_charges(dn_name=dn.name, service_code="03")
        else:
            frappe.msgprint("UPS Ground rates are not available. Please select other services")
        return shipping_rates
    except PyUPSException, e:
        """ e is PyUPSException obj returns tuple as structured (message, request, response)"""
        frappe.throw(e[0])

def get_rating_service(params):
    return RatingService(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        True                        # sandbox for testing purpose set as True for production set it to False
    )

def get_ups_rating_request(delivery_note, params):
    # prepate the ups rating request
    dn = delivery_note

    packing_slips = [row.packing_slip for row in dn.packing_slip_details]
    if not packing_slips:
        frappe.throw("Can not find the linked Packing Slip ...")

    ship_from_address_name = params.get("default_warehouse")
    shipper_number = params.get("shipper_number")
    package_type = ups_packages.get(params.get("package_type"))
    ship_to_params = {
        "customer":dn.customer,
        "contact_display":dn.contact_display,
        "contact_mobile":dn.contact_mobile
    }

    shipment = E.Shipment(
                    Helper.get_shipper(params),
                    Helper.get_ship_to_address(ship_to_params, dn.shipping_address_name,),
                    Helper.get_ship_from_address(params, ship_from_address_name),
                    RatingService.service_type(Code='03'),
                )
    packages = Helper.get_packages(packing_slips, package_type)
    shipment.extend(packages)

    rating_request = RatingService.rating_request_type(
        shipment,
    )

    return rating_request

def parse_xml_response_to_json(response):
    rates = {}

    for rated_shipment in response.iterchildren(tag='RatedShipment'):
        service = rated_shipment.find("Service")
        total_charges = rated_shipment.find("TotalCharges")

        if (service is not None) and (total_charges is not None):
            service_code = service.find("Code")
            service_charges = total_charges.find("MonetaryValue")

            rates.update({
                service_code.text: flt(service_charges.text)
            })
        else:
            frappe.throw("Can Not find the Service and Total Charges Attribute in RatedShipment")

    return rates

@frappe.whitelist()
def add_shipping_charges(dn_name=None, service_code=None, shipping_rate=None):
    dn = frappe.get_doc("Delivery Note",dn_name)
    # check if shipping overhead is already added
    charges_row = None
    shipping_charge = 0.0
    total_charge = 0.0
    rates = {}
    # check if shipping rates are available if not first fetch rates
    if dn.ups_rates:
        rates = json.loads(dn.ups_rates)

    # result = get_condition(rates, service_code)
    if rates.get(service_code) or service_code == "Manual":
        if service_code == "Manual":
            shipping_charge = flt(shipping_rate) or 0.0
        else:
            # rates = json.loads(dn.ups_rates)
            shipping_charge = rates.get(service_code) or 0.0

        defaults = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                                        ["default_account", "cost_center", "shipping_overhead"],
                                        as_dict=True)[0]
        total_charge = shipping_charge + (shipping_charge * (flt(defaults.get("shipping_overhead"))/100))

        for row in dn.taxes:
            condition = (row.charge_type == "Actual" and row.description == "Shipping Overhead"
                        and row.account_head == defaults.get("default_account")
                        and row.cost_center == defaults.get("cost_center"))

            # total_charge = shipping_charge + (shipping_charge * (flt(defaults.get("shipping_overhead"))/100))
            update_taxes_and_charges_row(row, total_charge, defaults)

            if condition:
                # remove row in service code is mannual
                charges_row = row

        if not charges_row:
            ch = dn.append('taxes', {})
            ch = update_taxes_and_charges_row(ch, total_charge, defaults)

        rates.update({
            "service_used":service_code
        })
        dn.ups_rates = json.dumps(rates)

        dn.is_manual_shipping = 1 if service_code == "Manual" else 0
        dn.carrier_shipping_rate = shipping_charge or 0.0
        dn.total_shipping_rate = total_charge

        dn.save(ignore_permissions=True)
    else:
        get_shipping_rates(dn_name, True)

    return "True"

def update_taxes_and_charges_row(row, shipping_charge, defaults):
    row.charge_type = "Actual"
    row.account_head = defaults.get("default_account")
    row.cost_center = defaults.get("cost_center")
    # row.rate = defaults.get("shipping_overhead")
    row.tax_amount = shipping_charge
    row.description = "Shipping Overhead"
    return row
