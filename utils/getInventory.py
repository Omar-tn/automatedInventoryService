import os
import csv
import requests
from dotenv import load_dotenv


def get_shopify_inventory():
    load_dotenv()

    store_url = os.getenv('SHOPIFY_STORE_URL')
    api_version = os.getenv('SHOPIFY_ADMIN_API_VERSION')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    base_url = f"https://{store_url}/admin/api/{api_version}"
    products_url = f"{base_url}/products.json"

    inventory_data = []

    response = requests.get(products_url, headers=headers)
    if response.status_code == 200:
        products = response.json()['products']
        for product in products:
            for variant in product['variants']:
                inventory_data.append({
                    'Handle': product['handle'],
                    'Title': product['title'],
                    'Option1 Name': variant.get('option1', ''),
                    'Option1 Value': variant.get('option1', ''),
                    'Option2 Name': variant.get('option2', ''),
                    'Option2 Value': variant.get('option2', ''),
                    'Option3 Name': variant.get('option3', ''),
                    'Option3 Value': variant.get('option3', ''),
                    'SKU': variant.get('sku', ''),
                    'HS Code': '',
                    'COO': '',
                    'Shop location': variant.get('inventory_quantity', 0),
                    'My Custom Location': 'not stocked',
                    'Snow City Warehouse': 'not stocked'
                })
    return inventory_data


def save_to_csv(data, filename):
    fieldnames = ['Handle', 'Title', 'Option1 Name', 'Option1 Value',
                  'Option2 Name', 'Option2 Value', 'Option3 Name',
                  'Option3 Value', 'SKU', 'HS Code', 'COO', 'Shop location',
                  'My Custom Location', 'Snow City Warehouse']

    with open(filename, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


if __name__ == "__main__":
    inventory_data = get_shopify_inventory()
    save_to_csv(inventory_data, 'inventory_export_1.csv')
