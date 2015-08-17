import frappe
from datetime import datetime as dt
from frappe.utils import formatdate
from frappe.utils.dateutils import datetime_in_user_format, get_user_date_format
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from frappe_subscription.frappe_subscription.ups_package_tracking import get_package_tracking_status

def track_and_update_packing_slip():
    # track packages and update the status
    # get all the packing_slips name
    now = dt.strptime(datetime_in_user_format(dt.now()), "%m-%d-%Y %H:%M")
    #scheduler_events should run on 8AM, 12PM, and 5PM
    condition = ((now > now.replace(hour=8, minute=0, second=0, microsecond=0) and
                now < now.replace(hour=9, minute=0, second=0, microsecond=0)) or
                (now > now.replace(hour=12, minute=0, second=0, microsecond=0) and
                now < now.replace(hour=13, minute=0, second=0, microsecond=0)) or
                (now > now.replace(hour=17, minute=0, second=0, microsecond=0) and
                now < now.replace(hour=18, minute=0, second=0, microsecond=0)))

    if condition:
        query = """SELECT DISTINCT ps.delivery_note, ps.name, ps.tracking_id
                FROM `tabPacking Slip` ps,`tabDelivery Note` dn WHERE ps.docstatus=1
                AND dn.docstatus=1 AND dn.is_manual_shipping = 0
                AND ps.tracking_status<>'Delivered'"""

        packing_slips = frappe.db.sql(query,as_dict=True)

        for ps in packing_slips:
            status = get_package_tracking_status(ps.get("tracking_id"))
            # status = get_package_tracking_status("1Z12345E1512345676")
            code = status.get("code")
            # update status
            query = """UPDATE `tabPacking Slip` SET tracking_status='%s'
                    WHERE name='%s'"""%(status.get("description"),ps.get("name"))
            frappe.db.sql(query)
            query = """UPDATE `tabPacking Slip Details` SET tracking_status='%s'
                    WHERE parent='%s' AND packing_slip='%s'"""%(status.get("description"),
                    ps.get("delivery_note"),ps.get("name"))
            frappe.db.sql(query)

            # check if status is in transit
            si_against_so = []
            if code == "I":
                query = """SELECT DISTINCT
                            si.parent,
                            si.sales_order
                        FROM
                            `tabSales Invoice Item` si,
                            `tabDelivery Note Item` dni
                        WHERE
                            dni.parent='%s'
                        AND si.sales_order=dni.against_sales_order
                        GROUP BY
                            si.sales_order"""%(ps.get("delivery_note"))

                sales_orders = frappe.db.get_values("Delivery Note Item", {"parent":ps.get("delivery_note")}, "against_sales_order", as_dict=True)
                sales_orders = list(set([so.get("against_sales_order") for so in sales_orders]))
                results = frappe.db.sql(query, as_dict=True)

                if results:
                    for res in results:
                        if res.get("sales_order") in sales_orders:
                            si_against_so.append(res.get("sales_order"))
                else:
                    si_against_so = sales_orders

            if si_against_so:
                for sales_order in si_against_so:
                    si = make_sales_invoice(source_name=sales_order, target_doc=None)
                    si.save(ignore_permissions=True)
                    print si.name
