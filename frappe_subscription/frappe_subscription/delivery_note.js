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

cur_frm.cscript.create_ups_shipping_labels = function(doc,cdt,cdn){
    if(doc.dn_status == "Draft"){
        frappe.throw("Bin Packing Information not found ...\n");
    }
    else if(doc.dn_status == "Shipping Labels Created"){
        frappe.throw("Shipping Labels are already Created ...\n");
    }
    else{
        return frappe.call({
            freeze: true,
            freeze_message:"Creating UPS Shipping Labels ...",
            method: "frappe_subscription.frappe_subscription.ups_shipping_package.get_shipping_labels",
            args:{
                delivery_note:doc.name,
            },
            callback: function(r){
                if(!r.exc) {
                    // cur_frm.reload_doc();
                    frappe.msgprint("Shipping Labels Created ....");
                }
            },
        });
    }
}

cur_frm.cscript.get_ups_rates = function(doc,cdt,cdn){
    if(doc.dn_status == "Draft"){
        frappe.throw("Bin Packing Information not found ...\n");
    }
    else if(doc.dn_status == "UPS Rates Fetched"){
        frappe.throw("UPS Rates are already Fetched ...\n");
    }
    else if(doc.dn_status == "Shipping Labels Created"){
        frappe.throw("Shipping Labels are already Created ...\n");
    }
    else{
        return frappe.call({
            freeze: true,
            freeze_message:"Fetching UPS Shipping Rates ...",
            method: "frappe_subscription.frappe_subscription.ups_shipping_rates.get_shipping_rates",
            args:{
                delivery_note:doc.name,
            },
            callback: function(r){
                if(!r.exc) {
                    // cur_frm.reload_doc();
                    frappe.msgprint("Fetched UPS Shipping Rates ....");
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
