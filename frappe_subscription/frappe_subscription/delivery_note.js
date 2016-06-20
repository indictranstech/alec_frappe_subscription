cur_frm.cscript.get_packing_details = function(doc,cdt,cdn){
    if(is_doc_saved()){
        if(doc.pack_manualy==1){
            doc.pack_manualy = 0
            refresh_field('pack_manualy')
        }
        frappe.throw("Please first save the Delivery Note");
    }
    // if(doc.name.indexOf("New Delivery Note") > -1)
    //     frappe.throw("Please first save the Delivery Note");
    else{
        if(doc.dn_status == "Draft" || doc.dn_status == "Partialy Packed"){
            confirm_msg = "<center>Do you really want to create the Packing Slips<br>\
                            Once Packing Slip Created you can not make changes in Delivery Note</center>"

            frappe.confirm(confirm_msg,function(){
                return frappe.call({
                    freeze: true,
                    freeze_message:"Fetching Bin Packing Information ...",
                    method: "frappe_subscription.bin_packing.get_bin_packing_details",
                    args:{
                        // delivery_note:doc.name,
                        delivery_note:doc,
                    },
                    callback: function(r){
                        if(!r.exc) {
                            cur_frm.reload_doc();
                            if(r.message.status == "Packing Slips Created")
                                frappe.msgprint("Packing Slip Created");
                        }
                    },
                });
            });
        }
        else
            frappe.throw("Packing Slips are already created. Please Reload the Document")
    }
}

cur_frm.cscript.fetch_ups_ground_rates = function(doc, cdt, cdn){
    // if(doc.name.indexOf("New Delivery Note") > -1)
    if(doc.is_manual_shipping)
        frappe.throw("Please uncheck the Manual Shipping Option");
    else if(is_doc_saved())
        frappe.throw("Please first save the Delivery Note");
    else if(doc.dn_status == "Draft")
        frappe.throw("Bin Packing Information not found ...\n");
    else{
        get_rates(doc, true, "Fetching UPS Ground Rate");
    }
}

cur_frm.cscript.get_ups_rates = function(doc,cdt,cdn){
    // if(doc.name.indexOf("New Delivery Note") > -1)
    if(doc.is_manual_shipping)
        frappe.throw("Please uncheck the Manual Shipping Option");
    else if(is_doc_saved())
        frappe.throw("Please first save the Delivery Note");
    else if(doc.dn_status == "Draft")
        frappe.throw("Bin Packing Information not found ...\n");
    else if(doc.dn_status == "Shipping Labels Created"){
        frappe.throw("Shipping Labels are already Created ...\n");
    }
    else{
        if(doc.ups_rates && doc.ups_rates != "{}"){
            new frappe.UPSShippingRates(JSON.parse(doc.ups_rates));
        }
        else{
            get_rates(doc, false, "Fetching UPS Shipping Rate");
        }
    }
}

get_rates = function(doc, is_ground, freeze_message){
    confirm_msg = "<center>Do you really want to get the UPS rates ?<br>\
                    You will not be able to Modify DN after Rates are Fetched</center>"
    frappe.confirm(confirm_msg, function(){
        return frappe.call({
            freeze: true,
            freeze_message:freeze_message,
            method: "frappe_subscription.frappe_subscription.ups_shipping_rates.get_shipping_rates",
            args:{
                // delivery_note:doc.name,
                delivery_note:doc,
                add_shipping_overhead: is_ground
            },
            callback: function(r){
                if(!r.exc) {
                    cur_frm.reload_doc();
                    if(!is_ground)
                        new frappe.UPSShippingRates(r.message);
                }
            },
        });
    })
}

// confirm_manual pack
cur_frm.cscript.pack_manualy = function(doc,cdt,cdn){
    if(doc.__islocal){
        doc.pack_manualy = 0
        refresh_field('pack_manualy')
        frappe.throw("Please first save Delivery Note...");
    }
    else{
        if(doc.status == "Draft" && (doc.dn_status == "Packing Slips Created" || doc.dn_status == "Manual Partialy Packed")){
                // if(doc.status == "Draft" && (doc.dn_status == "Draft" || doc.dn_status == "Partialy Packed")){
            confirm_msg = "<center>Do you really want to remove created Packing Slip ?</center>"

            frappe.confirm(confirm_msg,function(){
                return frappe.call({
                    freeze: true,
                    freeze_message:"Removing created Packing Slip...",
                    method: "frappe_subscription.frappe_subscription.manual_packing.pack_manualy",
                    args:{
                        delivery_note:doc,
                    },
                    callback: function(r){
                        refresh_field('pack_manualy')
                        refresh_field('packing_slip_details')
                        cur_frm.set_df_property("pack_manualy","read_only", 1)
                        window.location.reload()
                    }
                });
            }, function(){
                doc.pack_manualy = 0
                refresh_field('pack_manualy')
            });
        }
        else{
            frappe.throw("Please get Packing Details first before create Manual Packing")
        }
    }
}

// manual packing
cur_frm.cscript.manual_packing = function(doc,cdt,cdn){
    if(is_doc_saved())
        frappe.throw("Please first save Delivery Note..");
    else{
        if (doc.pack_manualy == 1){
            if(doc.status == "Draft" && (doc.dn_status == "Packing Slips Created" || doc.dn_status == "Manual Partialy Packed")){
                confirm_msg = "<center>Do you really want to create Manual Packing Slip ?</center>"
                frappe.confirm(confirm_msg,function(){
                    return frappe.call({
                        freeze: true,
                        freeze_message:"Manual Packing Creation...",
                        method: "frappe_subscription.frappe_subscription.manual_packing.manual_packing_creation",
                        args:{
                            delivery_note:doc,
                        },
                        callback: function(r){
                            if(r.message){
                                var di = new frappe.ui.Dialog({
                                    title: __("Manual Packing Details"),
                                    fields: [
                                        {"fieldtype": "Link", "label": __("Box"), "fieldname": "box", "width": "40px;"},
                                        {"fieldtype": "Column Break", "fieldname": "cb"},
                                        {"fieldtype": "Data", "label": __("Weight"), "fieldname": "weight"},
                                        {"fieldtype": "Column Break", "fieldname": "cb1"},
                                        {"fieldtype": "Data", "label": __("Total Items"), "fieldname": "tot_items"},
                                        {"fieldtype": "Column Break", "fieldname": "cb2"},
                                        {"fieldtype": "Data", "label": __("Total Weight"), "fieldname": "tot_wt"},
                                        {"fieldtype": "Section Break", "fieldname": "cb3"},
                                        {"fieldtype":"HTML", "label":__("Manual Packing"), "reqd":1, "fieldname":"manual_pack"},
                                        {"fieldtype": "Button", "label": __("Pack Items"), "fieldname": "pack_items"},
                                    ]
                                })
                                $(di.body).find("[data-fieldname='manual_pack']").html(frappe.render_template("manual_packing", {"data":r.message[0]}))
                                di.show();

                                $(di.body).find("[data-fieldname='box']").autocomplete({source: r.message[1]})

                                // set default selected qty as qty 
                                $.each(r.message[0], function(i, val) {
                                    $(di.body).find('input[name="select_qty"]').val(val.custom_qty)
                                })

                                format_fields(di);
                                search_boxes(di);
                                select_items(di);
                                change_qty(di);
                                cur_frm.refresh_fields();   
                                pack_items_manually(di,doc,r);
                            }
                        },
                    });
                });
            }
            else if(doc.status == "Draft" && doc.dn_status == "Manual Packing Slips Created"){
                frappe.throw("Manual Packing Slips are already created. Please Reload the Document")
            }
            else{
                frappe.throw("Please get Packing Details first before create Manual Packing")
            } 
        }
        else{
            frappe.throw("Please first remove created packing slip by confirming Pack manualy")
        }      
    }
}

// Pack Items Manually
pack_items_manually = function(di,doc,r){
    $(di.body).find("button[data-fieldname='pack_items']").on("click", function(){
        var chk_items = $('.check_row').find("input[name=check]:checked").closest('tr')
        if (chk_items.length > 0){
            if($('.t_row').length == chk_items.length){
                dn_status = "Manual Packing Slips Created"
                create_packing_slip_for_manual(di, doc, dn_status, chk_items, r)
            }
            else{
                dn_status = "Manual Partialy Packed"
                create_packing_slip_for_manual(di, doc, dn_status, chk_items, r)
            }
        }
        else{
            frappe.throw("Please first select items for Manual Packing...")
        }
    })
}

// create packing slip for manual packing
create_packing_slip_for_manual = function(di, doc, dn_status, chk_items, r){
    pack_items = []
    $.each(chk_items, function(i, row) {
        var item_row = row
        pack_item = $(row).find('td:eq(1)').html()
        c_uom = $(row).find('td:eq(2)').html()
        sel_qty = $(row).find('#select_qty').val()
        i = {"item_code": pack_item}
        uom = {"uom": c_uom}
        qty = {"qty": sel_qty}
        $.extend(i, uom);
        $.extend(i, qty);
        pack_items.push(i);
    })
    // get current values on dialog box
    box_item = $(di.body).find("input[data-fieldname='box']").val()
    box_wt = $(di.body).find("[data-fieldname='weight']").val()
    total_wt = $(di.body).find("[data-fieldname='tot_wt']").val()
    
    // Validation on selected Qty
    $.each(r.message[0], function(i, row) {
        $.each(pack_items, function(j, item_row) {
            if (row.item_code == item_row.item_code){
                if(row.custom_qty != item_row.qty){
                    frappe.throw("Selected Qty should not be greater than Actual Qty of Item...")
                }
            }
        })
    })
    if(Math.floor(box_wt) >= Math.floor(total_wt)){
        frappe.call({
            freeze: true,
            freeze_message:"Manual Packing Slip Creation ...",
            method:"frappe_subscription.frappe_subscription.manual_packing.create_packing_slip_for_manual",
            args:{
                "delivery_note":doc,
                "dn_status": dn_status,
                "pack_items": pack_items,
                "box_item": box_item,
                "box_wt": box_wt
            },
            callback: function(r) {
                if(r.message){
                    cur_frm.refresh_fields();
                    refresh_field('packing_slip_details')
                    di.hide()
                    window.location.reload()
                }
            }
        });
    }
    else{
        frappe.throw("Box Weigth should be greater then Total Weight of packing items..")
    }
}

// listuot box items
search_boxes = function(di){
    $(di.body).find("input[data-fieldname='box']").on("change", function(){
        box_item = $(di.body).find("input[data-fieldname='box']").val()
        if(box_item) {
            frappe.call({
                method:"frappe_subscription.frappe_subscription.manual_packing.get_box_item_wt",
                args:{
                    "box_item": box_item
                },
                callback: function(r) {
                    if(r.message){
                        $(di.body).find("[data-fieldname='weight']").val(r.message[0]['weight'])
                    }
                }
            });
        }
        else
            $(di.body).find("[data-fieldname='weight']").val(0)
    })
}

// calculate total wt and items on selected qty change
change_qty = function(di){
    $('.select_qty').on("change", function(){
        calculate_weigth(di)
     })   
   
}

// calculate total wt and items on selected items
select_items = function(di){
    var items = []
    $('.check_row').on("click", function(){
        calculate_weigth(di)
        if($('.check_row').find("input[name=check]:checked").length == 0){
            $(di.body).find("[data-fieldname='tot_items']").val(0)
            $(di.body).find("[data-fieldname='tot_wt']").val(0)
        }
    })
}

// actueal calculation on item selection and selected qty change
calculate_weigth = function(di){
    var tot_wt = 0
    var tot_qty = 0
    var item = $('.check_row').find("input[name=check]:checked").closest('tr')
    $.each(item, function(i, row) {
        i_code = $(row).find('td:eq(1)').html()
        sel_qty = $(row).find('#select_qty').val()
        if (sel_qty > 0 ){
            frappe.call({
                method:"frappe_subscription.frappe_subscription.manual_packing.calculate_total_weight",
                args:{
                    "item": i_code,
                    "select_qty": sel_qty
                },
                callback: function(r) {
                    if(r.message){
                        wt = r.message[1] * r.message[0]['weight']
                        tot_wt = tot_wt + wt
                        qty = r.message[1] * 1
                        tot_qty = tot_qty + qty
                    }
                    $(di.body).find("[data-fieldname='tot_items']").val(tot_qty)
                    $(di.body).find("[data-fieldname='tot_wt']").val(tot_wt)
                }
            });
        }
        else{
            $(row).find('#select_qty').val(1)
            frappe.throw("Selected quantity should not be 0 or less..")
        }
    })
}

// add classes and make fields readonly
format_fields = function(di){
    $(di.body).find("button[data-fieldname='pack_items']").css({"margin-left":"220px" ,"background-color": "#CED0D2", "border-radius": "8px", "width":"100px", "line-height": "1.7", "font-size":"15px"})

    // make fields readonly
    $(di.body).find("[data-fieldname='weight']").prop("readonly", true);
    $(di.body).find("[data-fieldname='tot_items']").prop("readonly", true);
    $(di.body).find("[data-fieldname='tot_wt']").prop("readonly", true);
}

// frappe.ui.form.on("Delivery Note Item", "refresh", function(doc, cdt, cdn) {
//     console.log("in refresh......")
//     console.log(cur_frm.doc.pack_manualy)
// });

frappe.ui.form.on("Delivery Note", "onload_post_render", function(doc, cdt, cdn) {
    var get_other_services = $(":button[data-fieldname='fetch_ups_ground_rates']");
    var get_bin_details = $(":button[data-fieldname='get_packing_details']");
    var get_ground_rates = $(":button[data-fieldname='get_ups_rates']");
    var pack_manualy = $(":button[data-fieldname='manual_packing']");
    // setting up the class
    get_bin_details.addClass("btn-primary");
    get_ground_rates.addClass("btn-primary");
    get_other_services.addClass("btn-primary");
    pack_manualy.addClass("btn-primary");

    if(cur_frm.doc.docstatus == 1 && cur_frm.doc.is_manual_shipping)
        cur_frm.get_field("packing_slip_details").grid.docfields[7].read_only = 0; // setting the tracking status field to editable
    else if (cur_frm.doc.docstatus == 0 && cur_frm.doc.is_manual_shipping)
        set_child_fields_to_readonly(0);    // removes the read only property
    else
        set_child_fields_to_readonly(1);    // setting the fields to read only
});

frappe.ui.form.on("Delivery Note Item", "item_code", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status != "Draft"){
        frappe.msgprint("Delivery Note is in Freezed State can not add new Item !!");
        cur_frm.fields_dict["items"].grid.grid_rows[cur_frm.doc.items.length - 1].remove();
    }
    else{
        // fetch custom UOM
        var me = this
        this.item = locals[cdt][cdn]
        frappe.call({
            method: "frappe_subscription.frappe_subscription.ec_item.get_default_uom",
            args: {
                item_code:item.item_code,
            },
            callback: function(r){
                item.custom_uom = r.message.uom;
                item.uom_conversion_rate = r.message.conversion_factor;
                window.setTimeout(function(){
                    me.item.custom_qty = calculate_custom_qty(me.item.qty, me.item.uom_conversion_rate);
                    item.qty_mapping = get_qty_wise_mapping_for_box(item.qty, item.custom_qty, item.uom_conversion_rate)
                    cur_frm.refresh_fields();
                }, 300)
            }
        });
    }
});

frappe.ui.form.on("Delivery Note", "onload", function(doc, cdt, cdn) {
    if (cur_frm.doc.pack_manualy==1){
        cur_frm.set_df_property("pack_manualy","read_only", 1)
    }
  var doc = locals[cdt][cdn];
  var items = doc.items;
  if(items){
    items.forEach(function(entry) {
      frappe.call({
        method: "frappe_subscription.frappe_subscription.ec_item.get_default_uom",
        args: {
          item_code: entry.item_code,
        },
      callback: function(r) {
        entry.custom_uom = r.message.uom,
        entry.uom_conversion_rate = r.message.conversion_factor,
        entry.custom_qty = calculate_custom_qty(entry.qty, entry.uom_conversion_rate),
        entry.qty_mapping = get_qty_wise_mapping_for_box(entry.qty, entry.custom_qty, entry.uom_conversion_rate),
        cur_frm.refresh_fields();
        }
      });
    })
  }
});


frappe.ui.form.on("Delivery Note Item", "items_remove", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status != "Draft"){
        frappe.msgprint("Did not save");
        cur_frm.reload_doc();
    }
});

frappe.ui.form.on("Delivery Note Item", "qty", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status != "Draft"){
        frappe.msgprint("Delivery Note is in Freezed State can not change the qty !!");
        cur_frm.fields_dict["items"].grid.grid_rows[cur_frm.doc.items.length - 1].remove();
        cur_frm.reload_doc();
    }
});

frappe.ui.form.on("Delivery Note", "shipping_address_name", function(doc, cdt, cdn) {
    dn_status = cur_frm.doc.dn_status;
    if(dn_status == "UPS Rates Fetched"){
        cur_frm.reload_doc();
        frappe.throw("UPS Shipping Rates are already fetched can not change the address");
    }
});

cur_frm.cscript.is_manual_shipping = function(doc,cdt,cdn){
    if(doc.is_manual_shipping){
        service = "Manual";
        doc.carrier_shipping_rate = 0.0;
        doc.total_shipping_rate = 0.0;
        cur_frm.refresh_field("carrier_shipping_rate")
        cur_frm.refresh_field("total_shipping_rate");
        set_child_fields_to_readonly(0);
    }
    else{
        service = "03";
        set_child_fields_to_readonly(1);
        set_up_taxes_and_charges(service, 0);
    }
}

cur_frm.cscript.carrier_shipping_rate = function(doc,cdt,cdn){
    if(doc.carrier_shipping_rate <= 0 && doc.is_manual_shipping == 1)
        frappe.msgprint("Invalid Shipping Rate")
    else
        set_up_taxes_and_charges(service, doc.carrier_shipping_rate)
}

set_child_fields_to_readonly = function(val){
    cur_frm.get_field("packing_slip_details").grid.docfields[6].read_only = val
    cur_frm.get_field("packing_slip_details").grid.docfields[8].read_only = val
    cur_frm.set_df_property("carrier_shipping_rate","read_only", val)
}

set_up_taxes_and_charges = function(code, rate){
    if(cur_frm.doc.name.indexOf("New Delivery Note") > -1)
    // if(is_doc_saved())
        frappe.throw("Please first save the Delivery Note");

    return frappe.call({
        freeze: true,
        freeze_message:"Setting Up Taxes and Charges ...",
        method:"frappe_subscription.frappe_subscription.ups_shipping_rates.add_shipping_charges",
        args:{
            dn_name: cur_frm.docname,
            service_code: code,
            shipping_rate: rate
        },
        callback: function(r){
            if(r.message) {
                if(r.message == "True")
                    msgprint("Shipping Charges are set in Taxes and Charges");
                cur_frm.reload_doc();
            }
        }
    });
}

is_doc_saved = function(){
    var is_saved = 1
    is_saved = locals["Delivery Note"][cur_frm.docname].__unsaved
    return is_saved
}

var service = ""

frappe.UPSShippingRates = Class.extend({
    // UPS Other Services Rates POP-UP
    init: function(rates) {
        this.make(rates);
    },
    make: function(rates) {
        shipping_rates = []

        var me = this;
        me.pop_up = this.render_pop_up_dialog(cur_frm.doc,me);

        this.append_pop_up_dialog_body(me.pop_up);
        this.append_shipping_charges(rates,cur_frm.doc);

        me.pop_up.show()
    },
    render_pop_up_dialog: function(doc, me){
        return new frappe.ui.Dialog({
            title: "Select Carrier Service",
            no_submit_on_enter: true,
            fields: [
                {label:__("Shipping Charges"), fieldtype:"HTML", fieldname:"charges"},
            ],

            primary_action_label: "Submit",
            primary_action: function() {
                // Update Clearance Date of the checked vouchers
                _me = this;
                me.pop_up.hide();
                set_up_taxes_and_charges(service, 0);
            }
        });
    },
    append_pop_up_dialog_body: function(pop_up){
        this.fd = pop_up.fields_dict;
        this.pop_up_body = $("<div id='container' style='overflow: auto;max-height: 300px;'>\
                            <table class='table table-bordered table-hover' id='entries'>\
                            <thead><th></th><th><b>Service Code</b></th><th><b>Service</b></th>\
                            <th><b>Charges</b></th></thead><tbody></tbody></table></div>").appendTo($(this.fd.charges.wrapper));
    },
    append_shipping_charges: function(ups_rates,doc){
        var rates = ups_rates
        service = rates["service_used"];
        if(!service)
            service = "03"
        service_mapper = {
            "01":"Next Day Air",
            "02":"2nd Day Air",
            "03":"Ground",
            "07":"Express",
            "08":"Expedited",
            "11":"UPS Standard",
            "12":"3 Day Select",
            "13":"Next Day Air Saver",
            "14":"Next Day Air Early A.M.",
            "54":"Express Plus",
            "59":"2nd Day Air A.M.",
            "65":"UPS Saver"
        }

        // sort by key
        services = []
        // $.each(rates, function(key, val){
        //     services.push(key)
        // });
        // services = services.sort()
        // sort by value
        var sortable = []
        for (var key in rates)
              sortable.push([key, rates[key]])
        sortable.sort(function(a, b) {return a[1] - b[1]})

        // for (var i = 0; i < services.length; i++) {
        //     code = services[i]
        //     desc = service_mapper[code];
        //     rate = rates[code]

        //     is_checked = (code == service) ? "checked" : "";
        //     if(code != "service_used"){
        //         $("<tr><td><input type='radio' name='service' value='"+ code +"' "+ is_checked +"></td>\
        //             <td align='center'>"+ code +"</td><td align='center'>"+ desc +"</td><td align='center'>"+
        //             rate +"</td></tr>").appendTo($("#entries tbody"))
        //     }
        // }

        for (var i = 0; i < sortable.length; i++) {
            code = sortable[i][0]
            desc = service_mapper[code];
            rate = rates[code]

            is_checked = (code == service) ? "checked" : "";
            if(code != "service_used"){
                $("<tr><td><input type='radio' name='service' value='"+ code +"' "+ is_checked +"></td>\
                    <td align='center'>"+ code +"</td><td align='center'>"+ desc +"</td><td align='center'>"+
                    rate +"</td></tr>").appendTo($("#entries tbody"))
            }
        }

        $(this.pop_up_body).find("[name='service']").click(function(){
            row = $(this).parent().parent();
            service = row.find("[name='service']").val()
        });
    },
});

cur_frm.fields_dict['items'].grid.get_field("custom_uom").get_query = function(doc, cdt, cdn) {
    item = locals[cdt][cdn]
    return {
        query: "frappe_subscription.frappe_subscription.ec_item.custom_uom_query",
        filters: {
            item_code: item.item_code
        }
    }
}

frappe.ui.form.on("Delivery Note Item", "custom_uom", function(frm, cdt, cdn){
    // set custom qty
    item = locals[cdt][cdn]
    frappe.call({
        method: "frappe_subscription.frappe_subscription.ec_item.get_conversion_factor",
        args: {
            item_code:item.item_code,
            uom: item.custom_uom
        },
        callback: function(r){
            item.uom_conversion_rate = r.message.conversion_factor
            item.custom_qty = calculate_custom_qty(item.qty, r.message.conversion_factor);
            item.qty_mapping = get_qty_wise_mapping_for_box(item.qty, item.custom_qty, item.uom_conversion_rate)
            cur_frm.refresh_fields();
        }
    });
})

frappe.ui.form.on("Delivery Note Item", "qty", function(frm, cdt, cdn){
    // set custom qty
    item = locals[cdt][cdn]
    item.custom_qty = calculate_custom_qty(item.qty, item.uom_conversion_rate);
    item.qty_mapping = get_qty_wise_mapping_for_box(item.qty, item.custom_qty, item.uom_conversion_rate)
    cur_frm.refresh_fields();
});

calculate_custom_qty = function(qty, conversion_factor){
    return Math.ceil(cint(qty) / cint(conversion_factor))
}

get_qty_wise_mapping_for_box = function(qty, custom_qty, conversion_factor){
    wt_mapping = {}
    $.each(Array(custom_qty), function(idx, item){
        if(qty < conversion_factor)
            wt_mapping[idx] = qty
        else{
            wt_mapping[idx] = conversion_factor
            qty = qty - conversion_factor
        }
    })
    return JSON.stringify(wt_mapping)
}
