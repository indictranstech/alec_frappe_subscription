cur_frm.cscript.after_cancel = function(doc,cdt,cdn){
    frappe.msgprint("Packing Slip is Cancelled and Deleted")
    frappe.set_route('List', "Packing Slip");
}

cur_frm.cscript.track_status = function(doc,cdt,cdn){
    if(doc.track_status == "Auto"){
        // cur_frm.set_df_property("tracking_id", "read_only", 1);
        cur_frm.set_df_property("tracking_status", "read_only", 1);
    }
    else{
        // cur_frm.set_df_property("tracking_id", "read_only", 0);
        cur_frm.set_df_property("tracking_status", "read_only", 0);
    }
}
