import frappe
from lxml.builder import E
from ups.shipping_package import ShipmentConfirm

class UPSHelper(object):
    """docstring for UPSHelper"""
    # TODO mappers

    @staticmethod
    def get_ups_api_params():
        params = frappe.db.get_values("Shipping Configuration","Shipping Configuration",
                            ["ups_user_name", "ups_password", "ups_license",
                            "shipper_number","default_warehouse", "user_name",
                            "attention_name","package_type"], as_dict=True)
        if not params[0]:
            frappe.throw("Shipping Configuration not found plase contact Administrator")
        else:
            user = params[0].get("ups_user_name")
            pwd = params[0].get("ups_password")
            license = params[0].get("ups_license")
            shipper_number = params[0].get("shipper_number")
            warehouse = params[0].get("default_warehouse")
            name = params[0].get("user_name")
            attention_name = params[0].get("attention_name")
            package_type = params[0].get("package_type") or "02"

            if user and pwd and license and shipper_number and warehouse and name and attention_name:
                return params[0]
            else:
                frappe.throw("Invalid UPS Configuration, Please contact Administrator")

    @staticmethod
    def get_shipper(params):
        if params:
            doc = frappe.get_doc("Warehouse",params.get("default_warehouse"))
            if not doc:
                frappe.throw("Can not fetch shipper Address")
            else:
                return ShipmentConfirm.shipper_type(
                    # shipper_address,
                    UPSHelper.get_address(doc, True),
                    Name= params.get("user_name"),
                    AttentionName= params.get("attention_name"),
                    # TaxIdentificationNumber="33065",
                    PhoneNumber= doc.phone_no,
                    ShipperNumber= params.get("shipper_number"),
                )
        else:
            frappe.throw("Shipper Address and Shipper Number fields required")

    @staticmethod
    def get_address(doc, is_ship_from= False):
        if is_ship_from:
            return ShipmentConfirm.address_type(
                AddressLine1= doc.address_line_1,
                AddressLine2= doc.address_line_2,
                City= doc.city,
                StateProvinceCode= doc.state,
                CountryCode= doc.country,
                PostalCode= doc.pin_code
            )
        else:
            return ShipmentConfirm.address_type(
                AddressLine1= doc.address_line1,
                AddressLine2= doc.address_line2,
                City= doc.city,
                StateProvinceCode= doc.state,
                CountryCode= frappe.db.get_value("Country",doc.country,"code"),
                PostalCode=str(doc.pincode),
            )

    @staticmethod
    def get_ship_to_address(params, address_name):
        doc = frappe.get_doc("Address", address_name)
        if not doc:
            frappe.throw("Can not fetch Customer Address")
        else:
            ship_to_address = UPSHelper.get_address(doc, False)

            return ShipmentConfirm.ship_to_type(
                ship_to_address,
                CompanyName= params.get("customer"),
                AttentionName= params.get("contact_display"),
                # TaxIdentificationNumber="",
                PhoneNumber= params.get("contact_mobile"),
            )

    @staticmethod
    def get_ship_from_address(params, address_name):
        doc = frappe.get_doc("Warehouse",address_name)
        if not doc:
            frappe.throw("Can not fetch Shipper Address")
        else:
            ship_from_address = UPSHelper.get_address(doc,True)

            return ShipmentConfirm.ship_from_type(
                ship_from_address,
                CompanyName= params.get("attention_name"),
                AttentionName= params.get("user_name"),
                # TaxIdentificationNumber="",
                PhoneNumber= doc.phone_no,
            )

    @staticmethod
    def get_packages(packing_slips, package_type_code):
        packages = []

        for docname in packing_slips:
            doc = frappe.get_doc("Packing Slip",docname)
            item = frappe.get_doc("Item", doc.package_used)
            package_ref = "%s/%s"%(doc.delivery_note, doc.name)

            package_weight = ShipmentConfirm.package_weight_type(
                Weight= str(doc.gross_weight_pkg), Code="LBS", Description="Weight In Pounds")

            dimensions = ShipmentConfirm.dimensions_type(
                Code="IN",
                Description="Deimensions In Inches",
                Length= str(item.length),
                Width= str(item.width),
                Height= str(item.height),
            )

            package_type = ShipmentConfirm.packaging_type(Code=package_type_code)

            package = ShipmentConfirm.package_type(
                package_type,
                package_weight,
                dimensions,
                # E.ReferenceNumber(E.Value(package_ref)),
            )

            packages.append(package)

        return packages

    @staticmethod
    def get_payment_info(type="prepaid", **kwargs):
        """Returns the payment info filled

        :param type: The payment type.

        .. note::
            if payment type is prepaid AccountNumber must be provided.
        """
        if type == 'prepaid':
            assert 'AccountNumber' in kwargs
            return ShipmentConfirm.payment_information_type(
                ShipmentConfirm.payment_information_prepaid_type(
                    AccountNumber=kwargs['AccountNumber'])
            )
        else:
            raise Exception("Type %s is not supported" % type)
