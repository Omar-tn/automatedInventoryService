import xml.etree.ElementTree as ET
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
import time
import backoff
import paramiko

from test import file_data


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


def getXml():


    hostname = "eu-central-1.sftpcloud.io"
    port = 22
    username = "e62abb7d4bce429db8fca4615b5f1ee3"
    password = "cHfW1YtDYLzRi5y27HnodSf4srN6guNN"
    file_data = None
    remote_file = "data.xml"
    try:
        transport = paramiko.Transport((hostname, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)

        with sftp.file(remote_file, mode='r') as remote:
            file_data= remote.read().decode('utf-8')

        user_input = input("Delete the XML file from the server after reading? (y/N): ").strip().lower()
        delete_after_read = user_input in ("y", "yes", "1")
        if delete_after_read:
            sftp.remove(remote_file)
            print(f"File '{remote_file}' deleted from SFTP server.")


        sftp.close()
        transport.close()
        return file_data
    except Exception as e:
        print(f"Error: {e}")

    return file_data

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

def parse_inventory_xml_from_string(xml_string):

    """Parse inventory data from XML string"""
    try:
        root = ET.fromstring(xml_string)
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
        print(f"Error parsing XML string: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error while parsing XML: {e}")
        raise


def update_shopify_inventory_bulk(inventory_data):
    """Update Shopify inventory in bulk"""
    load_dotenv()
    logs= []
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
                
                time.sleep(0.01)
            
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
                        log_entry = f"{datetime.now().isoformat()} | SKU: {sku} | Qty: {int (inventory_data[sku])}  -> Updated in Shopify"
                        print(log_entry)
                        logs.append(log_entry)

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

    return logs

def save_logs_to_file(logs: list, logs_dir: str = "logs") -> str:
    """
    Saves the logs to a text file with timestamped name.
    Returns the full path to the saved file.
    """
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs_{timestamp}.txt"
    log_path = os.path.join(logs_dir, log_filename)

    with open(log_path, "w", encoding="utf-8") as f:
        for log in logs:
            f.write(log + "\n")

    print(f" Logs saved to: {log_path}")
    return log_path

def upload_file_to_sftp(local_path,  remote_path=""):


    sftp_host="eu-central-1.sftpcloud.io"
    sftp_port=22
    sftp_username="e62abb7d4bce429db8fca4615b5f1ee3"
    sftp_password="cHfW1YtDYLzRi5y27HnodSf4srN6guNN"

    transport = paramiko.Transport((sftp_host, sftp_port))
    transport.connect(username=sftp_username, password=sftp_password)

    sftp = paramiko.SFTPClient.from_transport(transport)

    remote_file_path = os.path.join(remote_path, os.path.basename(local_path))
    sftp.put(local_path, remote_file_path)

    print(f"Uploaded log file to SFTP: {remote_file_path}")

    sftp.close()
    transport.close()

if __name__ == "__main__":
    try:
        # Get XML file from SFTP server and optionally delete it
        xml=getXml()
        inventory_data = parse_inventory_xml_from_string(xml)
        if inventory_data:
            logs=update_shopify_inventory_bulk(inventory_data)
        print(logs)
        path=save_logs_to_file(logs)
        upload_file_to_sftp(path)
    except Exception as e:
        print(f"Script failed: {str(e)}")