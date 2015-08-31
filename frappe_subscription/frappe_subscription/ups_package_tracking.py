import frappe
from lxml.builder import E
from frappe.utils import cstr
from lxml import etree, objectify
from ups.base import BaseAPIClient
from ups.base import PyUPSException
from frappe_subscription.frappe_subscription.ups_helper import UPSHelper as Helper

class TrackingRequest(BaseAPIClient):
    """Implements the Tracking Request"""

    # Indicates the action to be taken by the XML service.
    RequestAction = E.RequestAction('Track')
    RequestOption = E.RequestOption('all activity')

    # TransactionReference identifies transactions between client and server.
    TransactionReference = E.TransactionReference(
        E.CustomerContext('unspecified')
    )

    @property
    def url(self):
        """Returns the API URL by concatenating the base URL provided
        by :attr:`BaseAPIClient.base_url` and the
        :attr:`BaseAPIClient.sandbox` flag
        """
        return '/'.join([
            self.base_url[self.sandbox and 'sandbox' or 'production'],
            'Track']
        )

    @classmethod
    def tracking_request_type(cls, tracking_no, *args, **kwargs):
        request = E.Request(
            cls.RequestAction,
            kwargs.pop('RequestOption', cls.RequestOption),
            cls.TransactionReference,
        )
        return E.TrackRequest(
            request, tracking_no,*args, **kwargs
        )

    def request(self, track_request):
        """Calls up UPS and send the request. Get the returned response
        and return an element built out of it.

        :param rate_request: lxml element with data for the rate request
        """
        full_request = '\n'.join([
            '<?xml version="1.0" encoding="UTF-8" ?>',
            etree.tostring(self.access_request, pretty_print=True),
            '<?xml version="1.0" encoding="UTF-8" ?>',
            etree.tostring(track_request, pretty_print=True),
        ])

        self.logger.debug("Request XML: %s", full_request)

        # Send the request
        result = self.send_request(self.url, full_request)
        self.logger.debug("Response Received: %s", result)

        response = objectify.fromstring(result)
        self.look_for_error(response, full_request)

        # Return request ?
        if self.return_xml:
            return full_request, response
        else:
            return response

@frappe.whitelist()
def get_package_tracking_status(tracking_number=None):
    if not tracking_number:
        create_scheduler_log("Invalid Input", "get_package_tracking_status",
                            "Invalid Tracking Number %s : tracking number can not\
                            be None"%(tracking_number), tracking_number)
    else:
        try:
            params = Helper.get_ups_api_params()
            tracking_api = get_tracking_service(params)
            tracking_request = TrackingRequest.tracking_request_type(
                E.TrackingNumber(tracking_number),
            )
            response = tracking_api.request(tracking_request)
            return parse_xml_response_to_json(response, tracking_number)
        except PyUPSException, e:
            print "exception"
            create_scheduler_log(e[0], "get_package_tracking_status", tracking_number, e)

def get_tracking_service(params):
    return TrackingRequest(
        params.get("ups_license"),
        params.get("ups_user_name"),
        params.get("ups_password"),
        True                        # sandbox for testing purpose set as True for production set it to False
    )

def parse_xml_response_to_json(response, tracking_number):
    if response.find("Response").find("ResponseStatusCode").text == "1":
        shipment = response.find("Shipment")
        package = shipment.find("Package")
        activity = package.find("Activity")
        status_type = activity.find("Status").find("StatusType")
        #TODO return dict containing codes and discription
        return {
            "code": status_type.find("Code"),
            "description": status_type.find("Description")
        }
    elif response.find("Response").find("ResponseStatusCode").text == "0":
        error = response.find("Response").find("Error")
        err_security = error.find("ErrorSeverity").text or ""
        err_code = error.find("ErrorCode").text or ""
        desc = error.find("ErrorDescription").text or "No Tracking Information available"
        if err_security and err_code:
            msg = "%s-%s : %s"%(err_security, err_code, desc)
        else:
            msg = desc
        create_scheduler_log(msg, "parse_xml_response_to_json", tracking_number)

def create_scheduler_log(msg, method, tracking_id, obj=None):
	log = frappe.new_doc('Scheduler Log')
	log.method = method
	log.error = "Tracking ID : %s \nError : %s"%(tracking_id, msg)
	log.save(ignore_permissions=True)
