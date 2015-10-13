frappe.ui.form.on("Item", "unique_box_for_packing", function(frm){
    cur_frm.doc.box = "";
    cur_frm.set_df_property("box", "reqd", cur_frm.doc.unique_box_for_packing);
    cur_frm.refresh_fields();
});

frappe.ui.form.on("Item", "item_group", function(frm){
    if(cur_frm.doc.item_group == "Boxes"){
        cur_frm.doc.unique_box_for_packing = 0;
        cur_frm.set_df_property("box", "reqd", 0);
        cur_frm.refresh_fields(["unique_box_for_packing","box"]);
    }
});

cur_frm.fields_dict['box'].get_query = function(doc) {
    return {
        filters: {
            "item_group": "Boxes"
        }
    }
}
