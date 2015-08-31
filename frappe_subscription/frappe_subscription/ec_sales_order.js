cur_frm.fields_dict['items'].grid.get_field("item_code").get_query = function(doc) {
    return {
        filters: {
            "item_group": "Boxes"
        }
        //
        // filters = [
        //     ['Item', 'item_group', '!=', "Boxes"],
        // ];
    }
}
