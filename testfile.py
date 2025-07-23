import xml.etree.ElementTree as ET
import os
from wsgiref import headers

import requests
from dotenv import load_dotenv


def parse_inventory_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    inventory_data = {}

    namespace = {'inv': 'http://www.demandware.com/xml/impex/inventory/2007-05-31'}
    for record in root.findall('.//inv:record', namespace):
        product_id = record.get('product-id')
        allocation = record.find('inv:allocation', namespace).text
        inventory_data[product_id] = float(allocation)

    return inventory_data


def update_shopify_inventory(inventory_data):
    load_dotenv()

    store_url = os.getenv('SHOPIFY_STORE_URL')
    api_version = os.getenv('SHOPIFY_ADMIN_API_VERSION')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    base_url = f"https://{store_url}/admin/api/{api_version}"

    for product_id, quantity in inventory_data.items():
        inventory_item_id = get_inventory_item_id(product_id, base_url, headers)
        if inventory_item_id:
            update_url = f"{base_url}/inventory_levels/set.json"
            data = {
                "location_id": "80595517540",
                "inventory_item_id": inventory_item_id,
                "available": int(quantity)
            }
            response = requests.post(update_url, json=data, headers=headers)
            print(f"Updated inventory for {product_id}: {response.status_code}")
            # print(inventory_item_id)


def get_inventory_item_id(product_id, base_url, headers):


    search_url = f"{base_url}/variants.json?sku={product_id}"
    response = requests.get(search_url, headers=headers)

    if response.status_code == 200:
        variants = response.json().get('variants', [])

    for variant in variants:
        if variant.get('sku') == product_id:
            return variant['inventory_item_id']

    print(f"No variant found with SKU {product_id}")

    print(f"Error getting inventory item ID for SKU {product_id}: {response.status_code}")

    return None

if __name__ == "__main__":
    inventory_data = parse_inventory_xml('data.xml')
    update_shopify_inventory(inventory_data)
