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
    // else{
    //     cur_frm.doc.height = 0;
    //     cur_frm.doc.width = 0;
    //     cur_frm.doc.length = 0;
    // }
    // cur_frm.refresh_fields(["height", "width", "length"])
});

cur_frm.fields_dict['box'].get_query = function(doc) {
    return {
        filters: {
            "item_group": "Boxes"
        }
    }
}

frappe.ui.form.on("Custom UOM Conversion Details", "default_shipping_uom", function(frm, cdt, cdn){
    var me = this;
    doc = locals[cdt][cdn];
    is_checked = doc.default_shipping_uom;

    this.count = doc.default_shipping_uom;
    $.each(cur_frm.doc.custom_uoms, function(idx, item){
        if(item.name != cdn && item.default_shipping_uom == 1)
            me.count += 1
    })

    if(this.count > 1){
        frappe.msgprint("Only one UOM Conversion can be set as default");
        doc.default_shipping_uom = 0;
    }

    cur_frm.refresh_field("custom_uoms");
})
