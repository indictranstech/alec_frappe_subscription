
cur_frm.cscript.get_packing_details = function(doc,cdt,cdn){
    return frappe.call({
        method: "frappe_subscription.bin_packing.get_bin_packing_details",
        args:{
            delivery_note:doc.name,
        },
        callback: function(r){
            if(!r.exc) {
                cur_frm.reload_doc();
                frappe.msgprint("Packing Slip Created");
            }
        }
    });
}

frappe.ui.form.on("Delivery Note Item", "item_code", function(doc, cdt, cdn) {
    is_freezed = cur_frm.doc.is_freezed;
    if(is_freezed){
        frappe.msgprint("Delivery Note is in Freezed State can not new Item !!");
        cur_frm.fields_dict["items"].grid.grid_rows[cur_frm.doc.items.length - 1].remove();
    }
});

frappe.ui.form.on("Delivery Note Item", "items_remove", function(doc, cdt, cdn) {
    is_freezed = cur_frm.doc.is_freezed;
    if(is_freezed){
        frappe.msgprint("Delivery Note is in Freezed State can not delete item !!");
        cur_frm.reload_doc();
    }
});
