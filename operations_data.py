import requests
import pandas as pd
#import numpy as np
#----------------------------------------------------------------------------------------
# I. Fetch data from SevDesk
from config import API_KEY, API_BASE_URL

# Define the headers for the request
headers = {
    'Authorization': API_KEY,
    'Content-Type': 'application/json'
}

def get_invoices():
    url = f'{API_BASE_URL}/Invoice'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()
        
def get_invoice_positions():
    url = f'{API_BASE_URL}/InvoicePos'
    positions = []
    limit = 100  # standard limit. not too high, not too low
    offset = 0

    while True: # Request must be broken up into several pages because otherwise it is too large and does not work
        params = {
            'offset': offset,
            'limit': limit
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            positions.extend(data['objects'])
            if len(data['objects']) < limit:
                break
            offset += limit
        else:
            response.raise_for_status()
            break

    return positions

def get_customers():
    url = f'{API_BASE_URL}/Contact'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

def process_invoices(invoices):
    invoice_list = []
    for inv in invoices['objects']:
        invoice_list.append({
            'invoice_id': inv.get('id', None),
            'invoice_nr': inv.get('invoiceNumber', None),
            'invoice_date': inv.get('invoiceDate', None),
            'invoice_type': inv.get('invoiceType', None),
            'pay_date': inv.get('payDate', None),
            'customer_id': inv.get('contact', {}).get('id', None)
        })
    return pd.DataFrame(invoice_list)

def process_invoice_positions(invoice_positions):
    invoice_positions_list = []
    for pos in invoice_positions:
        invoice_positions_list.append({
            'invoice_id': pos.get('invoice', {}).get('id', None),
            'position_nr': pos.get('positionNumber', None),
            'item_name': pos.get('name', None),
            'item_id': pos.get('part', {}).get('id', None), 
            'quantity': pos.get('quantity', None),
            'price_net': pos.get('price', None),
            'tax_rate': pos.get('taxRate', None) 
        })
    return pd.DataFrame(invoice_positions_list)

def process_customers(customers):
    customers_list = []
    for cust in customers['objects']:
        customers_list.append({
            'customer_id': cust.get('id', None),
            'customer_name': cust.get('name', None)
        })
    return pd.DataFrame(customers_list)

def merge_dataframes(invoices_df, positions_df, customers_df):
    df1 = pd.merge(invoices_df, positions_df, on='invoice_id', how='outer')
    df = pd.merge(df1, customers_df, on='customer_id', how='left')
    return df.drop('invoice_id', axis='columns')

def format_data(df):
    cols = ['price_net', 'quantity', 'tax_rate']
    for col in cols:
        df[col] = pd.to_numeric(df[col])
    
    df['price_net_total'] = df['price_net'] * df['quantity']
    
    df = df.loc[:,['invoice_nr', 'invoice_type', 'invoice_date', 'pay_date', 
                   'position_nr', 'item_name', 'item_id', 'quantity', 
                   'price_net', 'tax_rate', 'price_net_total', 
                   'customer_name', 'customer_id']]
    
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    df['pay_date'] = pd.to_datetime(df['pay_date'], utc=True)
    
    return df

def get_sevdesk_data():
    invoices = get_invoices()
    invoice_positions = get_invoice_positions()
    customers = get_customers()
    
    invoices_df = process_invoices(invoices)
    positions_df = process_invoice_positions(invoice_positions)
    customers_df = process_customers(customers)
    
    df = merge_dataframes(invoices_df, positions_df, customers_df)
    df = format_data(df)
    
    return df

#-----------------------------------------------------------------------------------------------------

# II. Clean data

def clean_cancelled_invoices(df_clean):
    # Create a dataframe to keep track of cancelled invoices
    cancelled_invoices= {
        'cancelled_invoice': 'RE-1003', 
        'cancellation_invoice': 'RE-1072', 
        'new_invoice': 'RE-1073'
    }

    cancelled_invoices_df = pd.DataFrame([cancelled_invoices]) # Put the dict in a list as a workaround because it is only 1 row but pandas expects mutliple values per key.

    # Adjust invoice_date of new_invoice to match that of the corresponding cancelled_invoice
    # Merge dataframes
    mapping_df = cancelled_invoices_df.merge(
        df_clean[['invoice_nr', 'invoice_date']], 
        left_on='cancelled_invoice', 
        right_on='invoice_nr', 
        how='left'
    )

    # Turn mapping df into a dictionary that maps the new invoice to the invoice date of the cancelled invoice
    mapping_dict = mapping_df.set_index('new_invoice')['invoice_date'].to_dict()

    # Identify rows in df that match new_invoice from mapping_dict and update the invoice_date according to the mapping
    df_clean.loc[df_clean['invoice_nr'].isin(mapping_dict.keys()), 'invoice_date'] = df_clean['invoice_nr'].map(mapping_dict)

    # Drop the cancelled and cancellation invoices from df
    invoices_to_drop = (cancelled_invoices_df[['cancelled_invoice', 'cancellation_invoice']] # Tipp: Add parenthesis at the beginning, allows to break the code into multiple lines
                        .values # Values turns rows into lists, so we have as many lists as rows. 
                        .flatten()) # Flatten turns the list of lists into a single long list
    df_clean = df_clean[~df_clean['invoice_nr'].isin(invoices_to_drop)]
    return df_clean

def adjust_faulty_quantity(df_clean):
    # Adjust item_id of rows with 50% in item name
    df_clean.loc[df_clean['item_name'] == 'Sprossenschale Erbsen 50%', 'item_id'] = 33833158
    df_clean.loc[df_clean['item_name'] == 'Sprossenschale Radieschen 50%', 'item_id'] = 33833166

    # Adjust item_name and quantity where item_name contains 50%

    # 1 Create a mask to identify rows where 50% is in item_name
    mask = df_clean['item_name'].str.contains('50%')

    # 2 Adjust the quantity in these rows
    df_clean.loc[mask, 'quantity'] = df_clean.loc[mask, 'quantity']/2

    # 3 Remove '50%' from item_name column
    df_clean['item_name'] = df_clean['item_name'].str.replace('50%', '').str.strip() # strip removes leading and trailing spaces
    return df_clean

def add_missing_item_id(df_clean):
    # 1 Create dict to map correct item_id to item_name
    item_id_dict = df_clean.loc[:,['item_id', 'item_name']] # Select relevant columns
    item_id_dict['item_id'] = item_id_dict['item_id'].astype('float').astype('Int64') # First convert to float to handle NaN values, then to integer
    item_id_dict = item_id_dict.drop_duplicates()
    item_id_dict = item_id_dict.loc[(item_id_dict['item_name'].str.contains('Sprossenschale')) & ~item_id_dict['item_id'].isna()] # Select rows with correct name and id
    item_id_dict['item_name'] = item_id_dict['item_name'].str.replace('Sprossenschale ', '') # Remove 'Sprossenschale'
    item_id_dict = item_id_dict.set_index('item_name')['item_id'].to_dict() # Cast to_dict to the series 'item_name' with 'item_id' as the index to create the dictionary

    # Create function to update item_ids to be consistent
    def update_item_id(row): 
        for key in item_id_dict.keys():
            if key in row['item_name']: # check if keyword is in item_name
                return item_id_dict[key] # return corresponding item_id if keyword is in item_name, 
        return row['item_id'] # leave item_id as is if not

    df_clean['item_id'] = df_clean.apply(update_item_id,axis=1).astype('Int64')
    return df_clean

def adjust_item_names(df_clean):
    # Change 'Schale' to 'Sprossenschale' to have unanimous item names
    df_clean['item_name'] = df_clean['item_name'].str.replace('Schale', 'Sprossenschale')
    return df_clean

def create_columns(df_clean):
    # Create column to show Pflanzenart of tray, if it is one, Nan for all other cases
    # df_clean['green_type'] = np.where(df_clean['item_name'].str.contains('Sprossenschale'), df_clean['item_name'].str.split('Sprossenschale', n=1).str[1].str.strip(), 'Not Greens') # Split after Sprossenschale, but only once
    df_clean['green_type'] = df_clean['item_name'].apply(
        lambda x: x.split('Sprossenschale', 1)[1].strip() 
        if 'Sprossenschale' in x
        else 'Not Greens')
    df_clean['invoice_month'] = df_clean['invoice_date'].dt.strftime('%Y-%m')
    return df_clean

def clean_data(df):
    df_clean = df.copy()
    df_clean = clean_cancelled_invoices(df_clean)
    df_clean = adjust_faulty_quantity(df_clean)
    df_clean = add_missing_item_id(df_clean)
    df_clean = adjust_item_names(df_clean)
    df_clean = create_columns(df_clean)
    return df_clean

#----------------------------------------------------------------------------------------------
# Download Data
def fetch_clean_data():
    df = get_sevdesk_data()
    df_clean = clean_data(df)
    return df_clean

def create_csv(df_clean):
    df_clean.to_csv('invoice_positions.csv', sep=';', decimal=',')
