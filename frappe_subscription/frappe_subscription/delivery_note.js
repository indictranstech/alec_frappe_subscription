cur_frm.cscript.get_packing_details = function(doc,cdt,cdn){
    if(doc.name.indexOf("New Delivery Note") > -1)
        frappe.throw("Please first save the Delivery Note");
    else{
        return frappe.call({
            freeze: true,
            freeze_message:"Fetching Bin Packing Information ...",
            method: "frappe_subscription.bin_packing.get_bin_packing_details",
            args:{
                delivery_note:doc.name,
            },
            callback: function(r){
                if(!r.exc) {
                    cur_frm.reload_doc();
                    frappe.msgprint("Packing Slip Created");
                }
            },
        });
    }
}

frappe.ui.form.on("Delivery Note Item", "item_code", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status != "Draft"){
        frappe.msgprint("Delivery Note is in Freezed State can not new Item !!");
        cur_frm.fields_dict["items"].grid.grid_rows[cur_frm.doc.items.length - 1].remove();
    }
});

frappe.ui.form.on("Delivery Note Item", "items_remove", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status != "Draft"){
        frappe.msgprint("Delivery Note is in Freezed State can not delete item !!");
        cur_frm.reload_doc();
    }
});
