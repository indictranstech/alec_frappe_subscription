from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cint
from frappe import _
import json
from frappe.utils import getdate, validate_email_add, today,get_datetime,now
import datetime

# Confirm manual packing and removing existing pcking slip
@frappe.whitelist()
def pack_manualy(delivery_note):
	dn = frappe.get_doc(json.loads(delivery_note))
	delete_ps = []
	count = 0

	if dn.packing_slip_details:
		for ps in dn.packing_slip_details:
			if ps.packing_slip :
				unique_ps = frappe.db.sql("""select psi.item_code from `tabPacking Slip` ps, 
				`tabPacking Slip Item` psi where ps.name = psi.parent and ps.name = '%s' """%(ps.packing_slip),as_dict=1)
				for i in unique_ps:
					unique_item = frappe.db.get_value("Item", i['item_code'], ["unique_box_for_packing"])
				if unique_item == 0:
					delete_ps.append(ps)
		# delete created packing slips which have not unique box
		if delete_ps:
			[dn.remove(chlid_row) for chlid_row in delete_ps]
			pack_slip = frappe.get_doc("Packing Slip", chlid_row.packing_slip)
			if chlid_row.packing_slip == pack_slip.name:
				frappe.db.sql("""update `tabPacking Slip` set docstatus = 2 where name = '%s' """%(chlid_row.packing_slip))
				frappe.delete_doc("Packing Slip", chlid_row.packing_slip, force=True, ignore_permissions=True)
			
			dn.pack_manualy = 1
			dn.save(ignore_permissions = True)
		# update case no and tacking status of unique box packing slips
		if dn.packing_slip_details:
			for ps in dn.packing_slip_details:
				count = count + 1
				frappe.db.sql("""update `tabPacking Slip` set track_status = "Manual",from_case_no = '%s',  
					to_case_no = '%s' where name = '%s' """%(count,count,ps.packing_slip))
	return "Done...!!!"

# Get items to manual packing from DN
@frappe.whitelist()
def manual_packing_creation(delivery_note):
	dn = frappe.get_doc(json.loads(delivery_note))
	items = []
	remain = []
	# return items to manual packing
	if dn.dn_status == "Packing Slips Created" and dn.pack_manualy == 1 :
		for i in dn.items:
			not_unq_item = frappe.db.get_value("Item", i.item_code, ["unique_box_for_packing"])
			if not_unq_item == 0:
				items.append(i)
	elif dn.dn_status == "Manual Partialy Packed" and dn.pack_manualy == 1 :
		remain_items = frappe.db.sql("""select distinct psi.item_code from `tabPacking Slip` ps, `tabPacking Slip Item` psi, 
			`tabDelivery Note` dn, `tabDelivery Note Item` dni where ps.delivery_note = '%s' and dni.parent = dn.name 
			and psi.parent = ps.name """%(dn.name), as_list=1)
		for r in remain_items:
			remain.append(r[0])
		if remain_items:
			for i in dn.items:
				if i.item_code not in remain:
					# if remain_items[0]['item_code'] != i.item_code:
					items.append(i)
	
	# return Box items
	boxes = frappe.db.sql("""select i.name from `tabItem` i, `tabBin` b where i.name = b.item_code and 
		i.item_group = "Boxes" and b.actual_qty > 0 """,as_list=1)
	box_list = []
	box_list = [b[0] for b in boxes]

	return items, box_list

# Fetch weight values of items
@frappe.whitelist()
def calculate_total_weight(item,select_qty):
	wt = frappe.db.sql("""select cuom.weight from `tabCustom UOM Conversion Details` cuom, `tabItem` i where
		i.name = cuom.parent and cuom.default_shipping_uom = 1 and i.name = '%s' """%(item),as_dict=1)
	wt.append(select_qty)

	return wt

# Fetch weight values of box items
@frappe.whitelist()
def get_box_item_wt(box_item):
	box_wt = frappe.db.sql("""select cuom.weight from `tabCustom UOM Conversion Details` cuom, `tabItem` i where
		i.name = cuom.parent and cuom.default_shipping_uom = 1 and i.name = '%s' """%(box_item),as_dict=1)

	return box_wt

# Packing Slip creation for manual packing
@frappe.whitelist()
def create_packing_slip_for_manual(delivery_note, dn_status, pack_items, box_item, box_wt):
	dn = frappe.get_doc(json.loads(delivery_note))
	pack_items = json.loads(pack_items)
	# case_no = frappe.db.sql("""select from_case_no, to_case_no from `tabPacking Slip` order by name desc limit 1 """,as_list=1)
	case_no = frappe.db.sql("""select MAX(from_case_no), MAX(to_case_no) FROM `tabPacking Slip` where 
		delivery_note = '%s' AND docstatus=1"""%(dn.name),as_list=1)

	if dn.dn_status in ["Draft","Manual Partialy Packed", "Packing Slips Created"]:
		# calculate wt for each item
		for i in pack_items:
			item_wt = frappe.db.sql("""select cuom.weight, i.item_name,i.description from `tabCustom UOM Conversion Details` cuom, 
				`tabItem` i where i.name = cuom.parent and cuom.default_shipping_uom = 1 and i.name = '%s' """%(i['item_code']),as_dict=1)
			if item_wt:
				tot_wt = cint(i['qty']) * item_wt[0]['weight']
				i['wt'] = tot_wt
				i['item_name'] = item_wt[0]['item_name']
				i['desc'] = item_wt[0]['description']

		# Manual Packing Slip creation
		ps = frappe.new_doc("Packing Slip")
		ps.naming_series = "PS-"
		ps.delivery_note = dn.name
		ps.track_status = "Manual"
		if case_no:
			ps.from_case_no = cint(case_no[0][0]) + 1
			ps.to_case_no = cint(case_no[0][1]) + 1
		else:
			ps.from_case_no = 1
			ps.to_case_no =  1
		ps.tracking_id = "NA"
		ps.package_used = box_item
		ps.tracking_status = "Not Packed"
		ps.net_weight_pkg = box_wt
		ps.gross_weight_pkg = box_wt
		ps.set("items", [])
		for item in pack_items:
			ps_item = ps.append("items",{})
			ps_item.item_code = item['item_code']
			ps_item.item_name = item['item_name']
			ps_item.description = item['desc']
			ps_item.qty = cint(item['qty'])
			ps_item.net_weight = item['wt']
			ps_item.stock_uom = item['uom']
			
		ps.flags.ignore_permissions = 1
		ps.docstatus = 1
		ps.save()

		# add child table record of packing slip in DN
		psd = dn.append('packing_slip_details', {})
		psd.item_code = box_item
		psd.item_name = frappe.db.get_value("Item",box_item,"item_name")
		psd.packing_slip = ps.name
		psd.tracking_id = "NA"
		psd.tracking_status = "Not Packed"

		dn.dn_status = dn_status
		dn.save()
	elif dn.dn_status == "Manual Packing Slips Created" :
		frappe.throw("Manual Packing Slips are already created. Please Reload the Document")
	else:
		frappe.throw("Please get Packing Details first before create Manual Packing Slip")

	return "Done...!!!"