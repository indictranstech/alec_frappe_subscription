frappe.ui.form.on("Shipping Configuration", "ups_mode", function(doc) {
    msg = ""
    if(doc.ups_mode == "Sandbox")
        msg = "<center>Do you really want to set UPS API mode to <b>SANDBOX</b>?,<br>SANDBOX mode is for testing UPS API<center>";
    else
        msg = "<center>Do you really want to set UPS API mode to <b>PRODUCTION</b>?<br>After submitting the Delivery Note Shipment will be created at UPS</center>";

    frappe.confirm(msg, function(){}, function(){
        cur_frm.doc.ups_mode = cur_frm.doc.ups_mode == "Production"?"Sandbox":"Production";
        cur_frm.refresh_fields();
    })
});
