import frappe
from frappe.utils import flt, cint

def get_packing_slip_details(delivery_note, bin_algo_response= None):
    # 1: get packing bin data
    # 2: for each bin create separate packing slip then create the packing deatils
    #    for DN
    dn = frappe.get_doc("Delivery Note",delivery_note)

    if delivery_note and bin_algo_response:
        bins_packed = bin_algo_response.get("bins_packed")
        dn.set("packing_slip_details",[])
        for bin_info in bins_packed:
            ch = dn.append('packing_slip_details', {})

            ch.item_code = bin_info.get("bin_data").get("id")
            ch.item_name = frappe.db.get_value("Item",ch.item_code,"item_name")
            ch.packing_slip = create_packing_slip(delivery_note, bin_info)

        # freez tht delivery note
        dn.is_freezed = 1
        dn.save(ignore_permissions=True)
    return dn

def create_packing_slip(delivery_note, bin_detail):
    # get items and create the packing slip
    ps = frappe.new_doc("Packing Slip")
    ps.delivery_note = delivery_note
    case_no = get_recommended_case_no(delivery_note)
    ps.from_case_no, ps.to_case_no = case_no, case_no
    # total_weight = calculate_total_weight(bin_detail.get("bin_data"))
    total_weight = flt(bin_detail.get("bin_data").get("weight"))
    ps.net_weight_pkg, ps.gross_weight_pkg = total_weight, total_weight

    ps.set("items",[])
    ps.set("bin_items",[])

    items = {}

    # adding items to child table bin items
    for item in bin_detail.get("items"):
        ch_bin_item = ps.append("bin_items",{})
        ch_bin_item.item_code = item.get("id")
        ch_bin_item.item_name = frappe.db.get_value("Item",ch_bin_item.item_code,"item_name")
        ch_bin_item.image_sbs = "<img src='data:image/png;base64,%s'/>"%(item.get("image_sbs"))

        qty = 1
        if items.get(ch_bin_item.item_code):
            qty = items.get(ch_bin_item.item_code) + 1

        items.update({
            ch_bin_item.item_code:qty
        })

    # adding items
    for item,qty in items.iteritems():
        ch_item = ps.append("items",{})
        dn_item = frappe.db.get_values("Delivery Note Item",
                                    {"item_code":item,"parent":delivery_note},
                                    ["item_name","stock_uom","description",
                                    "batch_no"], as_dict= True)[0]

        ch_item.item_code = item
        ch_item.item_name = dn_item.get("item_name")
        ch_item.qty = qty
        ch_item.stock_uom = dn_item.get("stock_uom")
        ch_item.description = dn_item.get("description")
        ch_item.batch_no = dn_item.get("batch_no")

    ps.submit()

    return ps.name

# def calculate_total_weight(bin_data):
#     frappe.errprint(bin_data)
#     frappe.errprint([bin_data.get("weight"), bin_data.get("used_weight"),(bin_data.get("weight") * 0.01) * (bin_data.get("used_weight") / 100)])
#     return (bin_data.get("weight") * 0.01) * (bin_data.get("used_weight") / 100)

def get_recommended_case_no(delivery_note):
    """
        Returns the next case no. for a new packing slip for a delivery
        note
    """
    recommended_case_no = frappe.db.sql("""SELECT MAX(to_case_no) FROM `tabPacking Slip`
        WHERE delivery_note = %s AND docstatus=1""", delivery_note)

    return cint(recommended_case_no[0][0]) + 1

def on_packing_slip_cancel(doc, method):
    # delete the packing slip details entry from delivery note

    delivery_note = doc.delivery_note
    dn = frappe.get_doc("Delivery Note", delivery_note)

    if dn.docstatus == 1:
        frappe.throw("Packing Slip is Linked with Submitted Delivery Note : %s"%dn.name)
    elif dn.docstatus == 0:
        if dn.is_freezed:
            frappe.throw("Delivery Note is in Freezed state can not cancel the Packing Slip")
        else:
            to_remove = []
            for ps in dn.packing_slip_details:
                if ps.packing_slip == doc.name:
                    to_remove.append(ps)
            if to_remove:
                [dn.remove(ch) for ch in to_remove]
                dn.save(ignore_permissions = True)

                frappe.delete_doc("Packing Slip",doc.name)
