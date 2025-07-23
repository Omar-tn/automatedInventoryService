import csv
import random
import xml.etree.ElementTree as ET
from datetime import datetime


def read_inventory_csv(csv_file):
    inventory_data = {}
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['SKU']:
                inventory_data[row['SKU']] = float(row['Shop location'])
    return inventory_data


def create_inventory_xml(inventory_data):
    root = ET.Element('inventory')
    root.set('xmlns', 'http://www.demandware.com/xml/impex/inventory/2007-05-31')

    inventory_list = ET.SubElement(root, 'inventory-list')
    header = ET.SubElement(inventory_list, 'header')
    header.set('list-id', 'huda-inventory')

    default_instock = ET.SubElement(header, 'default-instock')
    default_instock.text = 'false'
    description = ET.SubElement(header, 'description')
    description.text = 'Inventory for Huda'
    use_bundle = ET.SubElement(header, 'use-bundle-inventory-only')
    use_bundle.text = 'false'
    on_order = ET.SubElement(header, 'on-order')
    on_order.text = 'true'

    records = ET.SubElement(inventory_list, 'records')

    for sku, quantity in inventory_data.items():
        record = ET.SubElement(records, 'record')
        record.set('product-id', sku)

        allocation = ET.SubElement(record, 'allocation')
        allocation.text = f"{random.randint(1,100):.2f}"

        timestamp = ET.SubElement(record, 'allocation-timestamp')
        timestamp.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        perpetual = ET.SubElement(record, 'perpetual')
        perpetual.text = 'false'

        handling = ET.SubElement(record, 'preorder-backorder-handling')
        handling.text = 'none'

    tree = ET.ElementTree(root)
    tree.write('data.xml', encoding='utf-8', xml_declaration=True)


if __name__ == "__main__":
    inventory_data = read_inventory_csv('inventory_export_1.csv')
    create_inventory_xml(inventory_data)
