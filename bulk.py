import xml.etree.ElementTree as ET
import os
import requests
from dotenv import load_dotenv
import time
import backoff

@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.ConnectionError, requests.exceptions.RequestException),
    max_tries=5
)
def make_request(session, method, url, **kwargs):
    """Make a request with retry logic"""
    response = session.request(method, url, **kwargs)
    response.raise_for_status()
    return response

def parse_inventory_xml(xml_file):
    """Parse inventory data from XML file"""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        inventory_data = {}

        namespace = {'inv': 'http://www.demandware.com/xml/impex/inventory/2007-05-31'}
        for record in root.findall('.//inv:record', namespace):
            product_id = record.get('product-id')
            allocation = record.find('inv:allocation', namespace)
            if allocation is not None:
                inventory_data[product_id] = float(allocation.text)

        print(f"Successfully parsed {len(inventory_data)} items from XML")
        return inventory_data
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error while parsing XML: {e}")
        raise

def update_shopify_inventory_bulk(inventory_data):
    """Update Shopify inventory in bulk"""
    load_dotenv()
    
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    location_id = os.getenv('SHOPIFY_LOCATION_ID')
    api_version = "2024-01"

    if not all([store_url, access_token, location_id]):
        raise ValueError("Missing required environment variables")

    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    with requests.Session() as session:
        session.headers.update(headers)
        base_url = f"https://{store_url}/admin/api/{api_version}"
        
        # Get inventory items for all SKUs
        all_skus = list(inventory_data.keys())
        variant_map = {}
        
        try:
            # Get variants in chunks of 50
            chunk_size = 50
            for i in range(0, len(all_skus), chunk_size):
                sku_chunk = all_skus[i:i + chunk_size]
                sku_list = ','.join(sku_chunk)
                
                variants_url = f"{base_url}/variants.json?fields=sku,inventory_item_id&limit=250&sku={sku_list}"
                response = make_request(session, 'GET', variants_url, timeout=(5, 15))
                
                for variant in response.json().get('variants', []):
                    if variant.get('sku') in inventory_data:
                        variant_map[variant['sku']] = variant['inventory_item_id']
                
                time.sleep(0.5)
            
            print(f"Found {len(variant_map)} matching variants")
            
            # Update inventory levels
            total_updated = 0
            for sku, inventory_item_id in variant_map.items():
                try:
                    # Remove the "inventory_level" wrapper from the request
                    update_data = {
                        "location_id": location_id,
                        "inventory_item_id": inventory_item_id,
                        "available": int(inventory_data[sku])
                    }
                    
                    response = session.post(
                        f"{base_url}/inventory_levels/set.json",
                        json=update_data,
                        timeout=(5, 15)
                    )
                    
                    if response.status_code == 200:
                        total_updated += 1
                        if total_updated % 5 == 0:
                            print(f"Updated {total_updated}/{len(variant_map)} items")
                    else:
                        print(f"Error updating SKU {sku}: {response.status_code} - {response.text}")
                    
                    # Rate limiting
                    if 'X-Shopify-Shop-Api-Call-Limit' in response.headers:
                        current, limit = map(int, response.headers['X-Shopify-Shop-Api-Call-Limit'].split('/'))
                        if current > (limit * 0.8):
                            time.sleep(1)
                        else:
                            time.sleep(0.25)
                            
                except requests.exceptions.RequestException as e:
                    print(f"Error updating SKU {sku}: {str(e)}")
                    time.sleep(1)
                    continue
                    
            print(f"\nInventory update complete:")
            print(f"Total items found in XML: {len(inventory_data)}")
            print(f"Total variants matched: {len(variant_map)}")
            print(f"Total items updated: {total_updated}")
            
            if len(inventory_data) != total_updated:
                print("\nSKUs not updated:")
                for sku in inventory_data.keys():
                    if sku not in variant_map:
                        print(f"- {sku}")
                        
        except Exception as e:
            print(f"Error during inventory update: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        inventory_data = parse_inventory_xml('data.xml')
        if inventory_data:
            update_shopify_inventory_bulk(inventory_data)
    except Exception as e:
        print(f"Script failed: {str(e)}")