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

cur_frm.cscript.get_ups_rates = function(doc,cdt,cdn){
    if(doc.dn_status == "Draft"){
        frappe.throw("Bin Packing Information not found ...\n");
    }
    else if(doc.dn_status == "UPS Rates Fetched"){
        new frappe.UPSShippingRates();
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
                    // TODO POP UP
                    new frappe.UPSShippingRates();
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

// Shipping Rates Pop Up
var service = ""

frappe.UPSShippingRates = Class.extend({
	init: function() {
		this.make();
	},
	make: function() {
		shipping_rates = []

		var me = this;
		me.pop_up = this.render_pop_up_dialog(cur_frm.doc,me);

		this.append_pop_up_dialog_body(me.pop_up);
		this.append_shipping_charges(cur_frm.doc);

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
    append_shipping_charges: function(doc){
        var rates = JSON.parse(doc.ups_rates);
        service = rates["service_used"];
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

        $.each(rates, function(key, val){
            code = key;
            desc = service_mapper[key];
            rate = val
            is_checked = (code == service) ? "checked" : "";

            if(code != "service_used"){
                $("<tr><td><input type='radio' name='service' value='"+ code +"' "+ is_checked +"></td>\
                    <td align='center'>"+ code +"</td><td align='center'>"+ desc +"</td><td align='center'>"+
                    rate +"</td></tr>").appendTo($("#entries tbody"))
            }
        })

        $(this.pop_up_body).find("[name='service']").click(function(){
            row = $(this).parent().parent();
            service = row.find("[name='service']").val()
        });
    },
});

cur_frm.cscript.is_manual_shipping = function(doc,cdt,cdn){
    if(doc.is_manual_shipping){
        service = "Manual";
        set_child_fields_to_readonly(0);
    }
    else{
        service = "03";
        set_child_fields_to_readonly(1);
        set_up_taxes_and_charges(service, doc.carrier_shipping_rate);
    }
}

cur_frm.cscript.carrier_shipping_rate = function(doc,cdt,cdn){
    set_up_taxes_and_charges(service, doc.carrier_shipping_rate)
}

set_child_fields_to_readonly = function(val){
    cur_frm.get_field("packing_slip_details").grid.docfields[5].read_only = val
    cur_frm.get_field("packing_slip_details").grid.docfields[7].read_only = val
    cur_frm.set_df_property("carrier_shipping_rate","read_only", val)
}

set_up_taxes_and_charges = function(code, rate){
    // if(service == "Manual")
    //     set_child_fields_to_readonly(0);
    // else
    //     set_child_fields_to_readonly(1)

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
            if(!r.exc) {
                msgprint("Shipping Overhead Set in Taxes and Charges");
                cur_frm.reload_doc();
            }
            else{
                msgprint("Error while saving the Shipping Overhead");
            }
        }
    });
}
