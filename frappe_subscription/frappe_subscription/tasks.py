import frappe
from datetime import datetime as dt
from frappe.utils import formatdate
from frappe.utils.dateutils import datetime_in_user_format, get_user_date_format, dateformats
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from frappe_subscription.frappe_subscription.ups_package_tracking import get_package_tracking_status

def track_and_update_packing_slip():
    # track packages and update the status
    # get all the packing_slips name
    date_format = convert_user_date_format()
    now = dt.strptime(datetime_in_user_format(dt.now()), date_format)
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

            if status:
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
        for user in sales_users:
            todo = frappe.new_doc("ToDo")
            todo.description = "Sales Invoice : %s Against Delivery Note: %s"%(sales_invoice,
                                delivery_note)
            todo.allocated_to = user.get("user_id")
            todo.assigned_by = "Administrator"
            todo.role = "Sales User"
            todo.reference_type = "Sales Invoice"
            todo.reference_name = sales_invoice
            todo.save(ignore_permissions=True)

def convert_user_date_format():
    user_format = get_user_date_format()
    datetime_format = dateformats[user_format]
    return datetime_format + " %H:%M"
