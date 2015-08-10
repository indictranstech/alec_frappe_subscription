import frappe
import httplib
import urllib
import json

from ec_packing_slip import get_packing_slip_details

params = {
    "images_background_color": "255,255,255",
    "images_bin_border_color": "59,59,59",
    "images_bin_fill_color": "230,230,230",
    "images_item_border_color": "214,79,79",
    "images_item_fill_color": "177,14,14",
    "images_item_back_border_color": "215,103,103",
    "images_sbs_last_item_fill_color": "99,93,93",
    "images_sbs_last_item_border_color": "145,133,133",
    "images_width": "100",
    "images_height": "100",
    "images_source": "base64",
    "images_sbs": "1",
    "stats": "1",
    "item_coordinates": "1",
    "images_complete": "1",
    "images_separated": "1"
}

def get_bin_packing_details(delivery_note, items):
    # check item group of item
    items_to_pack = []
    for item in items:
        item_details = frappe.db.get_values("Item",item.item_code,
                                            ["item_group", "unique_box_for_packing", "height", "width", "length", "weight_"],
                                            as_dict=True)
        if not item_details:
            frappe.throw("Invalid Item")
        else:
            item_group = item_details[0].get("item_group")
            uses_unique_packing_box = item_details[0].get("unique_box_for_packing") or 0
            if (item_group != "Boxes") and (not uses_unique_packing_box):
                height = item_details[0].get("height") or 0
                width = item_details[0].get("width") or 0
                depth = item_details[0].get("length") or 0
                weight = item_details[0].get("weight_") or 0

                if height and width and depth and weight:
                    # valid item continue with further processing
                    to_dict = {
                        "w": width, "h": height,
                        "d": depth, "q": item.qty,
                        "vr": 1, "id": item.item_code,
                        "wg": weight
                    }
                    items_to_pack.append(to_dict)
                else:
                    frappe.throw("Please set the valid dimension details for {0}-{1} item".format(item.item_code, item.item_name))

    if items_to_pack:
        # prepare 3d bin packing request in json format
        bins = get_bin_details()
        credentials = get_bin_packing_credentials()
        request = get_bin_packing_request(bins,items_to_pack,credentials,params)
        response = get_bin_packing_response(request)
        return get_packing_slip_details(delivery_note, response.get("response"))
    else:
        frappe.throw("No items found for bin packing process")

def get_bin_details():
    # get item with item group boxes
    # exclude the unique packing boxes
    bins = []

    query = """SELECT
                i.name, i.width, i.height, i.length, i.weight_
            FROM
                `tabItem` i,
                `tabBin` b
            WHERE
                i.item_group='Boxes'
            AND i.name NOT IN (SELECT box FROM `tabItem` WHERE unique_box_for_packing=1)
            AND b.item_code=i.item_code
            AND b.actual_qty>0"""

    items = frappe.db.sql(query,as_dict=True)

    for item in items:
        height = item.get('height')
        width = item.get("width")
        depth = item.get("length")
        weight = item.get("weight_")

        if height and width and depth and weight:
            bins.append({
                "id":item.name, "h":height,
                "w":width, "d":depth,
                "max_wg":weight
            })
        else:
            frappe.throw("Please set the valid dimension details for {0} item".format(item.name))

    return bins

def get_bin_packing_credentials():
    config = frappe.db.get_values("Shipping Configuration","Shipping Configuration",["binpacking_user_name","binpacking_api_key"],
                                as_dict=True)
    if not config:
        frappe.throw("Error while retrieving 3D Bin Packing Credentials Please check Shipping Configuration document")
    else:
        if config[0].get("binpacking_user_name") and config[0].get("binpacking_api_key"):
            # got valid username and api key
            return {
                "username": config[0].get("binpacking_user_name"),
                "api_key": config[0].get("binpacking_api_key")
            }
        else:
            frappe.throw("Invalid User Name and API Key for 3D Bin Packing")

def get_bin_packing_request(bins, items, credentials, params):
    return {
        "bins": bins,
        "items": items,
        "username": credentials.get("username"),
        "api_key": credentials.get("api_key"),
        "params": params
    }

c = """{
    "response": {
        "bins_packed": [{
            "bin_data": {
                "w": 12,
                "h": 12,
                "d": 24,
                "id": "ULINE 24x12x12",
                "used_space": 57.8704,
                "weight": 60,
                "used_weight": 75
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABiklEQVRYhZ3Y0XGDMBREUeggVgdm3AE0kOD+awp4EiOsvfue0P+Za0CSNRoGGjcaX0jGMsFgU\/rNOPWb0m\/Gqd+UfrNlpqcaP2y2xmMWY2GzZ1ZlVjaYmdFwhg1n0JgMGpMh4zJkXAaMzYCxGW18RhufkSbISBNklIkyykQZYcKMMGGmNXGmNXtG7hwzGswYg0+zoOGnYcMvDY15aWjMtyHjvg0ZNwXA2CkAxs40bfxM08ZPaGmCCS1NsG6UidaNMtHyFCZcnsKEu0Br4l2gNfFm0xg8cqzKfL\/OfCXeoKri+6flzfbT7kOfWY43nTZ\/mR6zVBMna\/4zHWap10HSvDN5c2Ty5sikTZVJmyqTNXUma+pM0pwySXPK5Mw5kzPnTMp8ZFLmI5My4sCSOOScMgnTZBKmycRmz\/QafQT1f1htJjRworb\/vyITGZUJjMwERma80RlvdMYayFgDGWco4wxljMGMMZhh88TMy1y4+rhPMCBz5VZmM92ZK5dMQ+nPXLkzG279mStXgL+bZbAiH9vGEwAAAABJRU5ErkJggg==",
            "images_generation_time": 0.00228,
            "packing_time": 0.07312,
            "items": [{
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAB0klEQVRYhZ3Y0W2EMBBFUbaD7HSwKKkAaCBsAxFJ\/60EAzZje56Zh6VI+eDoLvOBbHcdWk+0PiB5SA8WNsKbR88b4c2j543wZs30v29jfWOzNj6XoV4jNiEzW2bGJmQMMYwDNFvGMjM2OANNIwPNkalmsGaQiZnKzNjEtylNyACT3qY0MzaNoSHTGhoy7YxpLjKmUZlsBkfGMjqTmRkb\/TbaxIxhsrfRZsbmYmiWuRqaZULG+nC8B2hC5uKnVUZyszhMyLBGeLNlSCOluZ7BnuGM8ObIUEZqczWDmGGM8CZlCCOWac\/gzPiN8EZl3EZs05qBzniN8CbLaPO3DNP+N07p\/59tzyfIWDMYjZ\/m+CS+Omgmy4zGpB1f+FcHjc4kEzPALJaJGWIGKUOYlPGbM+M3Z8Yyk2VUxjKLZVTGMGVmMzpjmDITN3sp45xBlnGaLOMzecZn8kxpqqEFU2RKUw1t2E8WOlOYL3Mf0tcbFrXQQSnL5OYFSL3\/YjOZgZmG8R771HPejDbu0+X5oDujjP8Qm570Z05DnJXjo0QmGeZILnwmGurkL3zmMNwFg\/CZ3ZD3GMJnNsNelwifuXMrsxo6c+eSqRM+c+fOrHvymTtXgP+5oG9IoTujYQAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABdklEQVRYhZ3YwZGDMBBEUZHBujOAw+a1PtgZQPoL2IAE01I3OuvVd\/lAaSYldh7s\/FDSYSCHG\/imG3wD33SDb+CbOTO8ovPkZm78TsEZuVky78i8uaGZiRqe4YZnqKlkqKlkmKllmKlliKlmiKlmYlPPxKaeCU0jE5pGJjKtTGRamcA0M4FpZq6mnbmaJRN+OSZqlkzjp10MfLNkXAPfrBnTwDefjGfgm2\/GMvDNlnEMfLNnDAPfHBndwDdZRjbwTZ5RDXxTZJrmb33zwTFj8NOET2KfPDMG\/7Twhe+TZ7aMY7aMYfaMYfaMbo6Mbo6MbLKMbLKMavKMavKMaIqMaIqMZsqMZsqMZE4ZyZwyZxO+Q4brgyU7bFAqMqXpCbm+v9xMYWimYtSxL7unZnIjT5fHRTmTGX2I3W\/qmcMYs\/J21cjsxhnJ4Wc2Y03+8DNf4y0Y4Gc+xtxjwM+sxl2XwM\/c2crMxs7cWTIl+Jk7O7P08DN3VoD\/+as6xxq970IAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 10,
                    "y2": 10,
                    "z2": 10
                }
            }, {
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABtUlEQVRYhZ3Y23HDIBCFYdQB3g6kSSoAN2CSChz330qErgj2AEfMeMYP\/uYX+2BjjEHrgZaFZJAJLGyEN8PEG+HNMPFGeDNnaCO8iRnWCG+WDGmEN2uGM8KbLUMZ4c2eYYzw5sgQRnhzZvqN8CbJdBvhTZrpNcKbS6bTzJ\/6\/tEWNjHz65RVMXPm66kQ76GJmaBlAjYxoxHvoMEZbHAGmi1TziBgs2UK4x00+24KE7DZd5Mb76CpDA2aytCQqWd0U8+oJslcZxCwSTIX4x006W4uJmCT7iY13kHTGJpqGkPTTMyoXxxn2+dnPmk+WtZZHy0xz6YZDW8sb0bDG1ua1gxGwxvLm9HwxmqmPoPR8MbyZs8wxuqmNoMjQxjLmzPTbywyeAZJpttY3qSZ3Hyc+6yv8DneT+WBpTWDV5bpMD7PXM1bM0XmYuA3fMW8NfMqHi018AcryzRnoGRaRsu0jJZpGDVzmrdm1Mxh4OmozBwmzyxGz+wGHvaUTHUGIFMzKFMzKFMxMLOaYmjRwMxi4D8LPbOYP+0cgjPRjBNYIHPnVmY2dObOJZMRPnPnzsw8+MydK8B\/gp5t2krodwEAAAAASUVORK5CYII=",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABjElEQVRYhZ3Y0W3DMAyEYXuDRhtECLqAvUCbTpKHeINk\/UpBG8vW3ZE03z\/8QmA7hIaBzYnNByVjymS4SXEz5rhJcTPmuElxUzL5B803N6VxmcDM3NTMFZkrNzQzUcMz3PAMNSJDjcgwozLMqAwxMkOMzGCjM9joDDRGBhojg4yVQcbKAGNmgDEzvbEzvSmZzzuaiZqaWZ5ghKkZRB4Pamhm4YZmntTwDDc8Q43IUCMyzKgMMypDjMwQIzPY6Aw2OgONkYHGyCBjZZCxMsCYGWDMTG9qBn44FmS+XjtfMo\/WmPl9NL8pRzsPMTOvv7Tb\/GUiZm4eHK\/5zwTM3L4HTvPO+M2a8Zs14zZNxm2ajNe0Ga9pM06zyTjNJuMz24zPbDMus8u4zC7jMmBhscxtl3GYLuMwXcY2NRM1N7iC6j+sPmMakLEMylgGZQwDM4aBGW1wRhuckYZkpCEZZVhGGZYRhmaEoRlu7jTzMnAP4ZlqzpkMyRy5lSkmnDlyyTSkeObIndlwimeOXAH+Ao9Le7RjkPiSAAAAAElFTkSuQmCC",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "10",
                    "x2": 10,
                    "y2": 10,
                    "z2": 20
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 12,
                "d": 24,
                "id": "ULINE 24x12x12",
                "used_space": 57.8704,
                "weight": 60,
                "used_weight": 75
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABiklEQVRYhZ3Y0XGDMBREUeggVgdm3AE0kOD+awp4EiOsvfue0P+Za0CSNRoGGjcaX0jGMsFgU\/rNOPWb0m\/Gqd+UfrNlpqcaP2y2xmMWY2GzZ1ZlVjaYmdFwhg1n0JgMGpMh4zJkXAaMzYCxGW18RhufkSbISBNklIkyykQZYcKMMGGmNXGmNXtG7hwzGswYg0+zoOGnYcMvDY15aWjMtyHjvg0ZNwXA2CkAxs40bfxM08ZPaGmCCS1NsG6UidaNMtHyFCZcnsKEu0Br4l2gNfFm0xg8cqzKfL\/OfCXeoKri+6flzfbT7kOfWY43nTZ\/mR6zVBMna\/4zHWap10HSvDN5c2Ty5sikTZVJmyqTNXUma+pM0pwySXPK5Mw5kzPnTMp8ZFLmI5My4sCSOOScMgnTZBKmycRmz\/QafQT1f1htJjRworb\/vyITGZUJjMwERma80RlvdMYayFgDGWco4wxljMGMMZhh88TMy1y4+rhPMCBz5VZmM92ZK5dMQ+nPXLkzG279mStXgL+bZbAiH9vGEwAAAABJRU5ErkJggg==",
            "images_generation_time": 0.0017,
            "packing_time": 0.06685,
            "items": [{
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAB0klEQVRYhZ3Y0W2EMBBFUbaD7HSwKKkAaCBsAxFJ\/60EAzZje56Zh6VI+eDoLvOBbHcdWk+0PiB5SA8WNsKbR88b4c2j543wZs30v29jfWOzNj6XoV4jNiEzW2bGJmQMMYwDNFvGMjM2OANNIwPNkalmsGaQiZnKzNjEtylNyACT3qY0MzaNoSHTGhoy7YxpLjKmUZlsBkfGMjqTmRkb\/TbaxIxhsrfRZsbmYmiWuRqaZULG+nC8B2hC5uKnVUZyszhMyLBGeLNlSCOluZ7BnuGM8ObIUEZqczWDmGGM8CZlCCOWac\/gzPiN8EZl3EZs05qBzniN8CbLaPO3DNP+N07p\/59tzyfIWDMYjZ\/m+CS+Omgmy4zGpB1f+FcHjc4kEzPALJaJGWIGKUOYlPGbM+M3Z8Yyk2VUxjKLZVTGMGVmMzpjmDITN3sp45xBlnGaLOMzecZn8kxpqqEFU2RKUw1t2E8WOlOYL3Mf0tcbFrXQQSnL5OYFSL3\/YjOZgZmG8R771HPejDbu0+X5oDujjP8Qm570Z05DnJXjo0QmGeZILnwmGurkL3zmMNwFg\/CZ3ZD3GMJnNsNelwifuXMrsxo6c+eSqRM+c+fOrHvymTtXgP+5oG9IoTujYQAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABdklEQVRYhZ3YwZGDMBBEUZHBujOAw+a1PtgZQPoL2IAE01I3OuvVd\/lAaSYldh7s\/FDSYSCHG\/imG3wD33SDb+CbOTO8ovPkZm78TsEZuVky78i8uaGZiRqe4YZnqKlkqKlkmKllmKlliKlmiKlmYlPPxKaeCU0jE5pGJjKtTGRamcA0M4FpZq6mnbmaJRN+OSZqlkzjp10MfLNkXAPfrBnTwDefjGfgm2\/GMvDNlnEMfLNnDAPfHBndwDdZRjbwTZ5RDXxTZJrmb33zwTFj8NOET2KfPDMG\/7Twhe+TZ7aMY7aMYfaMYfaMbo6Mbo6MbLKMbLKMavKMavKMaIqMaIqMZsqMZsqMZE4ZyZwyZxO+Q4brgyU7bFAqMqXpCbm+v9xMYWimYtSxL7unZnIjT5fHRTmTGX2I3W\/qmcMYs\/J21cjsxhnJ4Wc2Y03+8DNf4y0Y4Gc+xtxjwM+sxl2XwM\/c2crMxs7cWTIl+Jk7O7P08DN3VoD\/+as6xxq970IAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 10,
                    "y2": 10,
                    "z2": 10
                }
            }, {
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABtUlEQVRYhZ3Y23HDIBCFYdQB3g6kSSoAN2CSChz330qErgj2AEfMeMYP\/uYX+2BjjEHrgZaFZJAJLGyEN8PEG+HNMPFGeDNnaCO8iRnWCG+WDGmEN2uGM8KbLUMZ4c2eYYzw5sgQRnhzZvqN8CbJdBvhTZrpNcKbS6bTzJ\/6\/tEWNjHz65RVMXPm66kQ76GJmaBlAjYxoxHvoMEZbHAGmi1TziBgs2UK4x00+24KE7DZd5Mb76CpDA2aytCQqWd0U8+oJslcZxCwSTIX4x006W4uJmCT7iY13kHTGJpqGkPTTMyoXxxn2+dnPmk+WtZZHy0xz6YZDW8sb0bDG1ua1gxGwxvLm9HwxmqmPoPR8MbyZs8wxuqmNoMjQxjLmzPTbywyeAZJpttY3qSZ3Hyc+6yv8DneT+WBpTWDV5bpMD7PXM1bM0XmYuA3fMW8NfMqHi018AcryzRnoGRaRsu0jJZpGDVzmrdm1Mxh4OmozBwmzyxGz+wGHvaUTHUGIFMzKFMzKFMxMLOaYmjRwMxi4D8LPbOYP+0cgjPRjBNYIHPnVmY2dObOJZMRPnPnzsw8+MydK8B\/gp5t2krodwEAAAAASUVORK5CYII=",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABjElEQVRYhZ3Y0W3DMAyEYXuDRhtECLqAvUCbTpKHeINk\/UpBG8vW3ZE03z\/8QmA7hIaBzYnNByVjymS4SXEz5rhJcTPmuElxUzL5B803N6VxmcDM3NTMFZkrNzQzUcMz3PAMNSJDjcgwozLMqAwxMkOMzGCjM9joDDRGBhojg4yVQcbKAGNmgDEzvbEzvSmZzzuaiZqaWZ5ghKkZRB4Pamhm4YZmntTwDDc8Q43IUCMyzKgMMypDjMwQIzPY6Aw2OgONkYHGyCBjZZCxMsCYGWDMTG9qBn44FmS+XjtfMo\/WmPl9NL8pRzsPMTOvv7Tb\/GUiZm4eHK\/5zwTM3L4HTvPO+M2a8Zs14zZNxm2ajNe0Ga9pM06zyTjNJuMz24zPbDMus8u4zC7jMmBhscxtl3GYLuMwXcY2NRM1N7iC6j+sPmMakLEMylgGZQwDM4aBGW1wRhuckYZkpCEZZVhGGZYRhmaEoRlu7jTzMnAP4ZlqzpkMyRy5lSkmnDlyyTSkeObIndlwimeOXAH+Ao9Le7RjkPiSAAAAAElFTkSuQmCC",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "10",
                    "x2": 10,
                    "y2": 10,
                    "z2": 20
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 12,
                "d": 24,
                "id": "ULINE 24x12x12",
                "used_space": 57.8704,
                "weight": 60,
                "used_weight": 75
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABiklEQVRYhZ3Y0XGDMBREUeggVgdm3AE0kOD+awp4EiOsvfue0P+Za0CSNRoGGjcaX0jGMsFgU\/rNOPWb0m\/Gqd+UfrNlpqcaP2y2xmMWY2GzZ1ZlVjaYmdFwhg1n0JgMGpMh4zJkXAaMzYCxGW18RhufkSbISBNklIkyykQZYcKMMGGmNXGmNXtG7hwzGswYg0+zoOGnYcMvDY15aWjMtyHjvg0ZNwXA2CkAxs40bfxM08ZPaGmCCS1NsG6UidaNMtHyFCZcnsKEu0Br4l2gNfFm0xg8cqzKfL\/OfCXeoKri+6flzfbT7kOfWY43nTZ\/mR6zVBMna\/4zHWap10HSvDN5c2Ty5sikTZVJmyqTNXUma+pM0pwySXPK5Mw5kzPnTMp8ZFLmI5My4sCSOOScMgnTZBKmycRmz\/QafQT1f1htJjRworb\/vyITGZUJjMwERma80RlvdMYayFgDGWco4wxljMGMMZhh88TMy1y4+rhPMCBz5VZmM92ZK5dMQ+nPXLkzG279mStXgL+bZbAiH9vGEwAAAABJRU5ErkJggg==",
            "images_generation_time": 0.00981,
            "packing_time": 0.07079,
            "items": [{
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAB0klEQVRYhZ3Y0W2EMBBFUbaD7HSwKKkAaCBsAxFJ\/60EAzZje56Zh6VI+eDoLvOBbHcdWk+0PiB5SA8WNsKbR88b4c2j543wZs30v29jfWOzNj6XoV4jNiEzW2bGJmQMMYwDNFvGMjM2OANNIwPNkalmsGaQiZnKzNjEtylNyACT3qY0MzaNoSHTGhoy7YxpLjKmUZlsBkfGMjqTmRkb\/TbaxIxhsrfRZsbmYmiWuRqaZULG+nC8B2hC5uKnVUZyszhMyLBGeLNlSCOluZ7BnuGM8ObIUEZqczWDmGGM8CZlCCOWac\/gzPiN8EZl3EZs05qBzniN8CbLaPO3DNP+N07p\/59tzyfIWDMYjZ\/m+CS+Omgmy4zGpB1f+FcHjc4kEzPALJaJGWIGKUOYlPGbM+M3Z8Yyk2VUxjKLZVTGMGVmMzpjmDITN3sp45xBlnGaLOMzecZn8kxpqqEFU2RKUw1t2E8WOlOYL3Mf0tcbFrXQQSnL5OYFSL3\/YjOZgZmG8R771HPejDbu0+X5oDujjP8Qm570Z05DnJXjo0QmGeZILnwmGurkL3zmMNwFg\/CZ3ZD3GMJnNsNelwifuXMrsxo6c+eSqRM+c+fOrHvymTtXgP+5oG9IoTujYQAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABdklEQVRYhZ3YwZGDMBBEUZHBujOAw+a1PtgZQPoL2IAE01I3OuvVd\/lAaSYldh7s\/FDSYSCHG\/imG3wD33SDb+CbOTO8ovPkZm78TsEZuVky78i8uaGZiRqe4YZnqKlkqKlkmKllmKlliKlmiKlmYlPPxKaeCU0jE5pGJjKtTGRamcA0M4FpZq6mnbmaJRN+OSZqlkzjp10MfLNkXAPfrBnTwDefjGfgm2\/GMvDNlnEMfLNnDAPfHBndwDdZRjbwTZ5RDXxTZJrmb33zwTFj8NOET2KfPDMG\/7Twhe+TZ7aMY7aMYfaMYfaMbo6Mbo6MbLKMbLKMavKMavKMaIqMaIqMZsqMZsqMZE4ZyZwyZxO+Q4brgyU7bFAqMqXpCbm+v9xMYWimYtSxL7unZnIjT5fHRTmTGX2I3W\/qmcMYs\/J21cjsxhnJ4Wc2Y03+8DNf4y0Y4Gc+xtxjwM+sxl2XwM\/c2crMxs7cWTIl+Jk7O7P08DN3VoD\/+as6xxq970IAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 10,
                    "y2": 10,
                    "z2": 10
                }
            }, {
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABtUlEQVRYhZ3Y23HDIBCFYdQB3g6kSSoAN2CSChz330qErgj2AEfMeMYP\/uYX+2BjjEHrgZaFZJAJLGyEN8PEG+HNMPFGeDNnaCO8iRnWCG+WDGmEN2uGM8KbLUMZ4c2eYYzw5sgQRnhzZvqN8CbJdBvhTZrpNcKbS6bTzJ\/6\/tEWNjHz65RVMXPm66kQ76GJmaBlAjYxoxHvoMEZbHAGmi1TziBgs2UK4x00+24KE7DZd5Mb76CpDA2aytCQqWd0U8+oJslcZxCwSTIX4x006W4uJmCT7iY13kHTGJpqGkPTTMyoXxxn2+dnPmk+WtZZHy0xz6YZDW8sb0bDG1ua1gxGwxvLm9HwxmqmPoPR8MbyZs8wxuqmNoMjQxjLmzPTbywyeAZJpttY3qSZ3Hyc+6yv8DneT+WBpTWDV5bpMD7PXM1bM0XmYuA3fMW8NfMqHi018AcryzRnoGRaRsu0jJZpGDVzmrdm1Mxh4OmozBwmzyxGz+wGHvaUTHUGIFMzKFMzKFMxMLOaYmjRwMxi4D8LPbOYP+0cgjPRjBNYIHPnVmY2dObOJZMRPnPnzsw8+MydK8B\/gp5t2krodwEAAAAASUVORK5CYII=",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABjElEQVRYhZ3Y0W3DMAyEYXuDRhtECLqAvUCbTpKHeINk\/UpBG8vW3ZE03z\/8QmA7hIaBzYnNByVjymS4SXEz5rhJcTPmuElxUzL5B803N6VxmcDM3NTMFZkrNzQzUcMz3PAMNSJDjcgwozLMqAwxMkOMzGCjM9joDDRGBhojg4yVQcbKAGNmgDEzvbEzvSmZzzuaiZqaWZ5ghKkZRB4Pamhm4YZmntTwDDc8Q43IUCMyzKgMMypDjMwQIzPY6Aw2OgONkYHGyCBjZZCxMsCYGWDMTG9qBn44FmS+XjtfMo\/WmPl9NL8pRzsPMTOvv7Tb\/GUiZm4eHK\/5zwTM3L4HTvPO+M2a8Zs14zZNxm2ajNe0Ga9pM06zyTjNJuMz24zPbDMus8u4zC7jMmBhscxtl3GYLuMwXcY2NRM1N7iC6j+sPmMakLEMylgGZQwDM4aBGW1wRhuckYZkpCEZZVhGGZYRhmaEoRlu7jTzMnAP4ZlqzpkMyRy5lSkmnDlyyTSkeObIndlwimeOXAH+Ao9Le7RjkPiSAAAAAElFTkSuQmCC",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "10",
                    "x2": 10,
                    "y2": 10,
                    "z2": 20
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 12,
                "d": 24,
                "id": "ULINE 24x12x12",
                "used_space": 57.8704,
                "weight": 60,
                "used_weight": 75
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABiklEQVRYhZ3Y0XGDMBREUeggVgdm3AE0kOD+awp4EiOsvfue0P+Za0CSNRoGGjcaX0jGMsFgU\/rNOPWb0m\/Gqd+UfrNlpqcaP2y2xmMWY2GzZ1ZlVjaYmdFwhg1n0JgMGpMh4zJkXAaMzYCxGW18RhufkSbISBNklIkyykQZYcKMMGGmNXGmNXtG7hwzGswYg0+zoOGnYcMvDY15aWjMtyHjvg0ZNwXA2CkAxs40bfxM08ZPaGmCCS1NsG6UidaNMtHyFCZcnsKEu0Br4l2gNfFm0xg8cqzKfL\/OfCXeoKri+6flzfbT7kOfWY43nTZ\/mR6zVBMna\/4zHWap10HSvDN5c2Ty5sikTZVJmyqTNXUma+pM0pwySXPK5Mw5kzPnTMp8ZFLmI5My4sCSOOScMgnTZBKmycRmz\/QafQT1f1htJjRworb\/vyITGZUJjMwERma80RlvdMYayFgDGWco4wxljMGMMZhh88TMy1y4+rhPMCBz5VZmM92ZK5dMQ+nPXLkzG279mStXgL+bZbAiH9vGEwAAAABJRU5ErkJggg==",
            "images_generation_time": 0.00168,
            "packing_time": 0.0666,
            "items": [{
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAB0klEQVRYhZ3Y0W2EMBBFUbaD7HSwKKkAaCBsAxFJ\/60EAzZje56Zh6VI+eDoLvOBbHcdWk+0PiB5SA8WNsKbR88b4c2j543wZs30v29jfWOzNj6XoV4jNiEzW2bGJmQMMYwDNFvGMjM2OANNIwPNkalmsGaQiZnKzNjEtylNyACT3qY0MzaNoSHTGhoy7YxpLjKmUZlsBkfGMjqTmRkb\/TbaxIxhsrfRZsbmYmiWuRqaZULG+nC8B2hC5uKnVUZyszhMyLBGeLNlSCOluZ7BnuGM8ObIUEZqczWDmGGM8CZlCCOWac\/gzPiN8EZl3EZs05qBzniN8CbLaPO3DNP+N07p\/59tzyfIWDMYjZ\/m+CS+Omgmy4zGpB1f+FcHjc4kEzPALJaJGWIGKUOYlPGbM+M3Z8Yyk2VUxjKLZVTGMGVmMzpjmDITN3sp45xBlnGaLOMzecZn8kxpqqEFU2RKUw1t2E8WOlOYL3Mf0tcbFrXQQSnL5OYFSL3\/YjOZgZmG8R771HPejDbu0+X5oDujjP8Qm570Z05DnJXjo0QmGeZILnwmGurkL3zmMNwFg\/CZ3ZD3GMJnNsNelwifuXMrsxo6c+eSqRM+c+fOrHvymTtXgP+5oG9IoTujYQAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABdklEQVRYhZ3YwZGDMBBEUZHBujOAw+a1PtgZQPoL2IAE01I3OuvVd\/lAaSYldh7s\/FDSYSCHG\/imG3wD33SDb+CbOTO8ovPkZm78TsEZuVky78i8uaGZiRqe4YZnqKlkqKlkmKllmKlliKlmiKlmYlPPxKaeCU0jE5pGJjKtTGRamcA0M4FpZq6mnbmaJRN+OSZqlkzjp10MfLNkXAPfrBnTwDefjGfgm2\/GMvDNlnEMfLNnDAPfHBndwDdZRjbwTZ5RDXxTZJrmb33zwTFj8NOET2KfPDMG\/7Twhe+TZ7aMY7aMYfaMYfaMbo6Mbo6MbLKMbLKMavKMavKMaIqMaIqMZsqMZsqMZE4ZyZwyZxO+Q4brgyU7bFAqMqXpCbm+v9xMYWimYtSxL7unZnIjT5fHRTmTGX2I3W\/qmcMYs\/J21cjsxhnJ4Wc2Y03+8DNf4y0Y4Gc+xtxjwM+sxl2XwM\/c2crMxs7cWTIl+Jk7O7P08DN3VoD\/+as6xxq970IAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 10,
                    "y2": 10,
                    "z2": 10
                }
            }, {
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABtUlEQVRYhZ3Y23HDIBCFYdQB3g6kSSoAN2CSChz330qErgj2AEfMeMYP\/uYX+2BjjEHrgZaFZJAJLGyEN8PEG+HNMPFGeDNnaCO8iRnWCG+WDGmEN2uGM8KbLUMZ4c2eYYzw5sgQRnhzZvqN8CbJdBvhTZrpNcKbS6bTzJ\/6\/tEWNjHz65RVMXPm66kQ76GJmaBlAjYxoxHvoMEZbHAGmi1TziBgs2UK4x00+24KE7DZd5Mb76CpDA2aytCQqWd0U8+oJslcZxCwSTIX4x006W4uJmCT7iY13kHTGJpqGkPTTMyoXxxn2+dnPmk+WtZZHy0xz6YZDW8sb0bDG1ua1gxGwxvLm9HwxmqmPoPR8MbyZs8wxuqmNoMjQxjLmzPTbywyeAZJpttY3qSZ3Hyc+6yv8DneT+WBpTWDV5bpMD7PXM1bM0XmYuA3fMW8NfMqHi018AcryzRnoGRaRsu0jJZpGDVzmrdm1Mxh4OmozBwmzyxGz+wGHvaUTHUGIFMzKFMzKFMxMLOaYmjRwMxi4D8LPbOYP+0cgjPRjBNYIHPnVmY2dObOJZMRPnPnzsw8+MydK8B\/gp5t2krodwEAAAAASUVORK5CYII=",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABjElEQVRYhZ3Y0W3DMAyEYXuDRhtECLqAvUCbTpKHeINk\/UpBG8vW3ZE03z\/8QmA7hIaBzYnNByVjymS4SXEz5rhJcTPmuElxUzL5B803N6VxmcDM3NTMFZkrNzQzUcMz3PAMNSJDjcgwozLMqAwxMkOMzGCjM9joDDRGBhojg4yVQcbKAGNmgDEzvbEzvSmZzzuaiZqaWZ5ghKkZRB4Pamhm4YZmntTwDDc8Q43IUCMyzKgMMypDjMwQIzPY6Aw2OgONkYHGyCBjZZCxMsCYGWDMTG9qBn44FmS+XjtfMo\/WmPl9NL8pRzsPMTOvv7Tb\/GUiZm4eHK\/5zwTM3L4HTvPO+M2a8Zs14zZNxm2ajNe0Ga9pM06zyTjNJuMz24zPbDMus8u4zC7jMmBhscxtl3GYLuMwXcY2NRM1N7iC6j+sPmMakLEMylgGZQwDM4aBGW1wRhuckYZkpCEZZVhGGZYRhmaEoRlu7jTzMnAP4ZlqzpkMyRy5lSkmnDlyyTSkeObIndlwimeOXAH+Ao9Le7RjkPiSAAAAAElFTkSuQmCC",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "10",
                    "x2": 10,
                    "y2": 10,
                    "z2": 20
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 12,
                "d": 24,
                "id": "ULINE 24x12x12",
                "used_space": 57.8704,
                "weight": 60,
                "used_weight": 75
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABiklEQVRYhZ3Y0XGDMBREUeggVgdm3AE0kOD+awp4EiOsvfue0P+Za0CSNRoGGjcaX0jGMsFgU\/rNOPWb0m\/Gqd+UfrNlpqcaP2y2xmMWY2GzZ1ZlVjaYmdFwhg1n0JgMGpMh4zJkXAaMzYCxGW18RhufkSbISBNklIkyykQZYcKMMGGmNXGmNXtG7hwzGswYg0+zoOGnYcMvDY15aWjMtyHjvg0ZNwXA2CkAxs40bfxM08ZPaGmCCS1NsG6UidaNMtHyFCZcnsKEu0Br4l2gNfFm0xg8cqzKfL\/OfCXeoKri+6flzfbT7kOfWY43nTZ\/mR6zVBMna\/4zHWap10HSvDN5c2Ty5sikTZVJmyqTNXUma+pM0pwySXPK5Mw5kzPnTMp8ZFLmI5My4sCSOOScMgnTZBKmycRmz\/QafQT1f1htJjRworb\/vyITGZUJjMwERma80RlvdMYayFgDGWco4wxljMGMMZhh88TMy1y4+rhPMCBz5VZmM92ZK5dMQ+nPXLkzG279mStXgL+bZbAiH9vGEwAAAABJRU5ErkJggg==",
            "images_generation_time": 0.00168,
            "packing_time": 0.06662,
            "items": [{
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAB0klEQVRYhZ3Y0W2EMBBFUbaD7HSwKKkAaCBsAxFJ\/60EAzZje56Zh6VI+eDoLvOBbHcdWk+0PiB5SA8WNsKbR88b4c2j543wZs30v29jfWOzNj6XoV4jNiEzW2bGJmQMMYwDNFvGMjM2OANNIwPNkalmsGaQiZnKzNjEtylNyACT3qY0MzaNoSHTGhoy7YxpLjKmUZlsBkfGMjqTmRkb\/TbaxIxhsrfRZsbmYmiWuRqaZULG+nC8B2hC5uKnVUZyszhMyLBGeLNlSCOluZ7BnuGM8ObIUEZqczWDmGGM8CZlCCOWac\/gzPiN8EZl3EZs05qBzniN8CbLaPO3DNP+N07p\/59tzyfIWDMYjZ\/m+CS+Omgmy4zGpB1f+FcHjc4kEzPALJaJGWIGKUOYlPGbM+M3Z8Yyk2VUxjKLZVTGMGVmMzpjmDITN3sp45xBlnGaLOMzecZn8kxpqqEFU2RKUw1t2E8WOlOYL3Mf0tcbFrXQQSnL5OYFSL3\/YjOZgZmG8R771HPejDbu0+X5oDujjP8Qm570Z05DnJXjo0QmGeZILnwmGurkL3zmMNwFg\/CZ3ZD3GMJnNsNelwifuXMrsxo6c+eSqRM+c+fOrHvymTtXgP+5oG9IoTujYQAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABdklEQVRYhZ3YwZGDMBBEUZHBujOAw+a1PtgZQPoL2IAE01I3OuvVd\/lAaSYldh7s\/FDSYSCHG\/imG3wD33SDb+CbOTO8ovPkZm78TsEZuVky78i8uaGZiRqe4YZnqKlkqKlkmKllmKlliKlmiKlmYlPPxKaeCU0jE5pGJjKtTGRamcA0M4FpZq6mnbmaJRN+OSZqlkzjp10MfLNkXAPfrBnTwDefjGfgm2\/GMvDNlnEMfLNnDAPfHBndwDdZRjbwTZ5RDXxTZJrmb33zwTFj8NOET2KfPDMG\/7Twhe+TZ7aMY7aMYfaMYfaMbo6Mbo6MbLKMbLKMavKMavKMaIqMaIqMZsqMZsqMZE4ZyZwyZxO+Q4brgyU7bFAqMqXpCbm+v9xMYWimYtSxL7unZnIjT5fHRTmTGX2I3W\/qmcMYs\/J21cjsxhnJ4Wc2Y03+8DNf4y0Y4Gc+xtxjwM+sxl2XwM\/c2crMxs7cWTIl+Jk7O7P08DN3VoD\/+as6xxq970IAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 10,
                    "y2": 10,
                    "z2": 10
                }
            }, {
                "id": "3M 7772ES",
                "w": 10,
                "h": 10,
                "d": 10,
                "wg": 30,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABtUlEQVRYhZ3Y23HDIBCFYdQB3g6kSSoAN2CSChz330qErgj2AEfMeMYP\/uYX+2BjjEHrgZaFZJAJLGyEN8PEG+HNMPFGeDNnaCO8iRnWCG+WDGmEN2uGM8KbLUMZ4c2eYYzw5sgQRnhzZvqN8CbJdBvhTZrpNcKbS6bTzJ\/6\/tEWNjHz65RVMXPm66kQ76GJmaBlAjYxoxHvoMEZbHAGmi1TziBgs2UK4x00+24KE7DZd5Mb76CpDA2aytCQqWd0U8+oJslcZxCwSTIX4x006W4uJmCT7iY13kHTGJpqGkPTTMyoXxxn2+dnPmk+WtZZHy0xz6YZDW8sb0bDG1ua1gxGwxvLm9HwxmqmPoPR8MbyZs8wxuqmNoMjQxjLmzPTbywyeAZJpttY3qSZ3Hyc+6yv8DneT+WBpTWDV5bpMD7PXM1bM0XmYuA3fMW8NfMqHi018AcryzRnoGRaRsu0jJZpGDVzmrdm1Mxh4OmozBwmzyxGz+wGHvaUTHUGIFMzKFMzKFMxMLOaYmjRwMxi4D8LPbOYP+0cgjPRjBNYIHPnVmY2dObOJZMRPnPnzsw8+MydK8B\/gp5t2krodwEAAAAASUVORK5CYII=",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABkBAMAAABtDuNZAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABjElEQVRYhZ3Y0W3DMAyEYXuDRhtECLqAvUCbTpKHeINk\/UpBG8vW3ZE03z\/8QmA7hIaBzYnNByVjymS4SXEz5rhJcTPmuElxUzL5B803N6VxmcDM3NTMFZkrNzQzUcMz3PAMNSJDjcgwozLMqAwxMkOMzGCjM9joDDRGBhojg4yVQcbKAGNmgDEzvbEzvSmZzzuaiZqaWZ5ghKkZRB4Pamhm4YZmntTwDDc8Q43IUCMyzKgMMypDjMwQIzPY6Aw2OgONkYHGyCBjZZCxMsCYGWDMTG9qBn44FmS+XjtfMo\/WmPl9NL8pRzsPMTOvv7Tb\/GUiZm4eHK\/5zwTM3L4HTvPO+M2a8Zs14zZNxm2ajNe0Ga9pM06zyTjNJuMz24zPbDMus8u4zC7jMmBhscxtl3GYLuMwXcY2NRM1N7iC6j+sPmMakLEMylgGZQwDM4aBGW1wRhuckYZkpCEZZVhGGZYRhmaEoRlu7jTzMnAP4ZlqzpkMyRy5lSkmnDlyyTSkeObIndlwimeOXAH+Ao9Le7RjkPiSAAAAAElFTkSuQmCC",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "10",
                    "x2": 10,
                    "y2": 10,
                    "z2": 20
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 10,
                "d": 18,
                "id": "ULINE 18x12x10",
                "used_space": 23.7037,
                "weight": 80,
                "used_weight": 88.8889
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABUklEQVRYheXY25GDMBBEUZHBMhlYtRnYESzOP6bF2ICEelrT+vX8n7pUUTxGKaGZZjI\/kKQ5k8FmuunGdDNl3Zhupqwb082akc2ayb\/Pdoh5ZfJyb4aZLdOSx8M3XmYhxsvcfeNmiHEzvvEzvvEzriEZ15CMZ1jGMyzjGJpxDM1gwzPY8Aw0nQw0nQwyWwY80Qsx1rk0YLaMaEw374xmTDefjGRMN3tGMaabIyMY082ZiRvTTZEJG\/tWU\/yLRc0fvj2hV9UthU2ZCZoqEzRVJmbqTMzUmZC5ZELmkomYayZirpmAaTIB02T6ps30TZvpGpDpGpDpmSfIVAZ8t1GmNOyPv8yUxnySDZv4YnEalqku7TTC\/nKYeOYwypq0GyGzG2kbMz3zMdrSZ3rmbcTd0vTMZkZWWDEzsl2\/jJoZOSxYjZwZOftIpmdGjnISOzGaMfkH41BF3pL\/mCQAAAAASUVORK5CYII=",
            "images_generation_time": 0.00105,
            "packing_time": 0.06648,
            "items": [{
                "id": "AC 1089-94-13-52",
                "w": 8,
                "h": 8,
                "d": 8,
                "wg": 80,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABn0lEQVRYhcXY7W2DMBSFYbNBuRuA2glsL1C3E9Dsv0rBicHmfuCDKtVSlF+P3nCjEGznpDWMxnoTiRtnY8lmmHBDuBlm3BBuhhk3hJs1A5s1M3988WWYLTN\/e7Yss2XeIyMh6CZnEs8kw+QMJ8HrRs0YRs3opmTOM0iGKZnIMqrZryayjGr2q4ksoxl9aLrRh6YaM6MYMyObOlPPIBmmzlQmeN00V1OZZJjmag4TvG5yRvhFJ8OQOWjR5AxoCDfPzGFihyHcvDKQIdyUDDIDws2eAQzh5sj0z4BwU2W6Df2VuZjBv5r48P6RX+n17kP1LCaahXc+5a+n61Y1Odks3NQZyVh33skpHW6aTJ9pM32mzXSZU4abhZtThhnrb35yslm4OWfOxnpqKZmOGbDMteGZa8Mzl0bItGbhRsg0xnpErjKN+eH\/21KmNtYTf52pDelkJtn0bywOY2Waj3YYYP+ym\/7MbpBtUjFAphhoN0Z45mWwTR\/hmacB95aEZ7K5s4UFM3d215tBM3cOC1YDZ+6cfTjCM3eOcpx1YjTK5Bd0cEfxxuvJyAAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABUklEQVRYheXYS5KDMAyEYXODQTeIF3OwWYQbJNcfQgLYuNVWexvtv\/qponjIKaGZZjI\/kKQ5k8FmuunGdDNl3Zhupqwb082akc2ayb\/3doh5ZfLybIaZLdOSx8M3XmYhxss8feNmiHEzvvEzvvEzriEZ15CMZ1jGMyzjGJpxDM1gwzPY8Aw0nQw0nQwyWwY80Qsx1rk0YLaMaEw374xmTDefjGRMN3tGMaabIyMY082ZiRvTTZEJG\/tWU\/yLRc0fvj2hV9UthU2ZCZoqEzRVJmbqTMzUmZC5ZELmkomYayZirpmAaTIB02T6ps30TZvpGpDpGpDpmTvIVAZ8t1GmNOyPv8yUxnySDZv4YnEalqku7TTC\/nKYeOYwypq0GyGzG2kbMz3zMdrSZ3rmbcTd0vTMZkZWWDEzsl2\/jJoZOSxYjZwZOftIpmdGjnISOzGaMfkHq2+9R1GXKNgAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 8,
                    "y2": 8,
                    "z2": 8
                }
            }]
        }, {
            "bin_data": {
                "w": 12,
                "h": 10,
                "d": 18,
                "id": "ULINE 18x12x10",
                "used_space": 23.7037,
                "weight": 80,
                "used_weight": 88.8889
            },
            "image_complete": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABUklEQVRYheXY25GDMBBEUZHBMhlYtRnYESzOP6bF2ICEelrT+vX8n7pUUTxGKaGZZjI\/kKQ5k8FmuunGdDNl3Zhupqwb082akc2ayb\/Pdoh5ZfJyb4aZLdOSx8M3XmYhxsvcfeNmiHEzvvEzvvEzriEZ15CMZ1jGMyzjGJpxDM1gwzPY8Aw0nQw0nQwyWwY80Qsx1rk0YLaMaEw374xmTDefjGRMN3tGMaabIyMY082ZiRvTTZEJG\/tWU\/yLRc0fvj2hV9UthU2ZCZoqEzRVJmbqTMzUmZC5ZELmkomYayZirpmAaTIB02T6ps30TZvpGpDpGpDpmSfIVAZ8t1GmNOyPv8yUxnySDZv4YnEalqku7TTC\/nKYeOYwypq0GyGzG2kbMz3zMdrSZ3rmbcTd0vTMZkZWWDEzsl2\/jJoZOSxYjZwZOftIpmdGjnISOzGaMfkH41BF3pL\/mCQAAAAASUVORK5CYII=",
            "images_generation_time": 0.001,
            "packing_time": 0.07038,
            "items": [{
                "id": "AC 1089-94-13-52",
                "w": 8,
                "h": 8,
                "d": 8,
                "wg": 80,
                "image_separated": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABn0lEQVRYhcXY7W2DMBSFYbNBuRuA2glsL1C3E9Dsv0rBicHmfuCDKtVSlF+P3nCjEGznpDWMxnoTiRtnY8lmmHBDuBlm3BBuhhk3hJs1A5s1M3988WWYLTN\/e7Yss2XeIyMh6CZnEs8kw+QMJ8HrRs0YRs3opmTOM0iGKZnIMqrZryayjGr2q4ksoxl9aLrRh6YaM6MYMyObOlPPIBmmzlQmeN00V1OZZJjmag4TvG5yRvhFJ8OQOWjR5AxoCDfPzGFihyHcvDKQIdyUDDIDws2eAQzh5sj0z4BwU2W6Df2VuZjBv5r48P6RX+n17kP1LCaahXc+5a+n61Y1Odks3NQZyVh33skpHW6aTJ9pM32mzXSZU4abhZtThhnrb35yslm4OWfOxnpqKZmOGbDMteGZa8Mzl0bItGbhRsg0xnpErjKN+eH\/21KmNtYTf52pDelkJtn0bywOY2Waj3YYYP+ym\/7MbpBtUjFAphhoN0Z45mWwTR\/hmacB95aEZ7K5s4UFM3d215tBM3cOC1YDZ+6cfTjCM3eOcpx1YjTK5Bd0cEfxxuvJyAAAAABJRU5ErkJggg==",
                "image_sbs": "iVBORw0KGgoAAAANSUhEUgAAAGUAAABbBAMAAACYIlYhAAAAG1BMVEX\/\/\/87Ozvm5uaxDg7WT0\/XZ2eRhYVjXV3IyMiQHr0rAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABUklEQVRYheXYS5KDMAyEYXODQTeIF3OwWYQbJNcfQgLYuNVWexvtv\/qponjIKaGZZjI\/kKQ5k8FmuunGdDNl3Zhupqwb082akc2ayb\/3doh5ZfLybIaZLdOSx8M3XmYhxss8feNmiHEzvvEzvvEzriEZ15CMZ1jGMyzjGJpxDM1gwzPY8Aw0nQw0nQwyWwY80Qsx1rk0YLaMaEw374xmTDefjGRMN3tGMaabIyMY082ZiRvTTZEJG\/tWU\/yLRc0fvj2hV9UthU2ZCZoqEzRVJmbqTMzUmZC5ZELmkomYayZirpmAaTIB02T6ps30TZvpGpDpGpDpmTvIVAZ8t1GmNOyPv8yUxnySDZv4YnEalqku7TTC\/nKYeOYwypq0GyGzG2kbMz3zMdrSZ3rmbcTd0vTMZkZWWDEzsl2\/jJoZOSxYjZwZOftIpmdGjnISOzGaMfkHq2+9R1GXKNgAAAAASUVORK5CYII=",
                "coordinates": {
                    "x1": "0",
                    "y1": "0",
                    "z1": "0",
                    "x2": 8,
                    "y2": 8,
                    "z2": 8
                }
            }]
        }],
        "errors": [],
        "status": 1,
        "not_packed_items": [],
        "response_time": 0.51796
    }
}"""

def get_bin_packing_response(request):
    return json.loads(c)
    connection = httplib.HTTPConnection(host='eu.api.3dbinpacking.com', port=80)
    req_params =  urllib.urlencode({'query':json.dumps(request)})
    headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
    connection.request("POST", "/packer/packIntoMany", req_params, headers)
    content = connection.getresponse().read()
    connection.close()

    response = json.loads(content)
    if response.get("response").get("status") == 1:
        return response
    else:
        frappe.throw("Error !!")
