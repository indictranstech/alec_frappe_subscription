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

            if code == "I":
                si = make_sales_invoice(source_name=ps.get("delivery_note"), target_doc=None)
                si.save(ignore_permissions=True)
                create_todo(si.name, ps.get("delivery_note"))

            # check if status is in transit
            # si_against_so = []
            # if code == "I":
            #     query = """SELECT DISTINCT
            #                 si.parent,
            #                 si.sales_order
            #             FROM
            #                 `tabSales Invoice Item` si,
            #                 `tabDelivery Note Item` dni
            #             WHERE
            #                 dni.parent='%s'
            #             AND si.sales_order=dni.against_sales_order
            #             GROUP BY
            #                 si.sales_order"""%(ps.get("delivery_note"))
            #
            #     sales_orders = frappe.db.get_values("Delivery Note Item", {"parent":ps.get("delivery_note")}, "against_sales_order", as_dict=True)
            #     sales_orders = list(set([so.get("against_sales_order") for so in sales_orders]))
            #     results = frappe.db.sql(query, as_dict=True)
            #
            #     if results:
            #         for res in results:
            #             if res.get("sales_order") in sales_orders:
            #                 si_against_so.append(res.get("sales_order"))
            #     else:
            #         si_against_so = sales_orders
            #
            # if si_against_so:
            #     for sales_order in si_against_so:
            #         si = make_sales_invoice(source_name=sales_order, target_doc=None)
            #         si.save(ignore_permissions=True)

def create_todo(sales_invoice, delivery_note):
    query = """SELECT DISTINCT
                emp.user_id
            FROM
                `tabSales Team` team,
                `tabEmployee` emp,
                `tabSales Person` per
            WHERE
                team.parent='%s'
            AND per.name=team.sales_person
            AND emp.name=per.employee"""%(delivery_note)

    sales_users = frappe.db.sql(query,as_dict=True)
    if not sales_users:
        create_scheduler_log("Can not create ToDo","create_todo",
                            "Can not found sales person users")
    else:
        for user in sales_user:
            todo = frappe.new_doc("ToDo")
            todo.description = "Sales Invoice : %s Against Delivery Note: %s"%(sales_invoice,
                                delivery_note)
            todo.allocated_to = user
            todo.assigned_by = "Administrator"
            todo.role = "Sales User"
            todo.reference_type = "Sales Invoice"
            todo.reference_name = sales_invoice
            todo.save(ignore_permissions=True)

def create_scheduler_log(msg, method, obj=None):
	log = frappe.new_doc('Scheduler Log')
	log.method = method
	log.error = msg
	log.obj_traceback = cstr(obj)
	log.save(ignore_permissions=True)
