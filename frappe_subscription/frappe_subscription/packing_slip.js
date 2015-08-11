cur_frm.cscript.after_cancel = function(doc,cdt,cdn){
    frappe.msgprint("Packing Slip is Cancelled and Deleted")
    frappe.set_route('List', "Packing Slip");
}
