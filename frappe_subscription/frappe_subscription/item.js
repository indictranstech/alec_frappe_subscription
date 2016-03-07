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

cur_frm.fields_dict['custom_uoms'].grid.get_field("uom").get_query = function(doc, cdt, cdn) {
    return {
        filters:[
            ['UOM', 'name', 'in', ["Nos", "Box"]],
        ]
    }
}

frappe.ui.form.on("Custom UOM Conversion Details", "default_shipping_uom", function(frm, cdt, cdn){
    var me = this;
    doc = locals[cdt][cdn];
    is_checked = doc.default_shipping_uom;

    $.each(cur_frm.doc.custom_uoms, function(idx, item){
        if(item.name != cdn && item.default_shipping_uom == 1)
            item.default_shipping_uom = 0
    })
    cur_frm.refresh_field("custom_uoms");
})

frappe.ui.form.on("Custom UOM Conversion Details", "uom", function(frm, cdt, cdn){
    doc = locals[cdt][cdn];

    row_count = 0
    cur_frm.doc.custom_uoms.map(function(row, idx){
        if(row.uom == doc.uom)
            row_count += 1
    })

    console.log(row_count)
    if(row_count > 1){
        frappe.msgprint(doc.uom+" Custom UOM Conversion Details is already added");
        cur_frm.fields_dict["custom_uoms"].grid.grid_rows[cur_frm.doc.custom_uoms.length - 1].remove();
    }

    if(doc.uom == "Nos")
        doc.conversion_factor = 1

    cur_frm.refresh_field("custom_uoms");
});