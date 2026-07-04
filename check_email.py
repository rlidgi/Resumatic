#!/usr/bin/env python3
"""Quick script to check if an email exists in Azure Users table."""
import os
from azure.data.tables import TableClient

# Load from .env
from dotenv import load_dotenv
load_dotenv()

connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
table_name = 'Users'

try:
    table_client = TableClient.from_connection_string(connection_string, table_name)
    
    # Query for profile rows with the email
    email_to_find = 'ronliogi@mail.com'
    query = f"RowKey eq 'profile' and email eq '{email_to_find}'"
    
    results = list(table_client.query_entities(query))
    
    if results:
        print(f"✓ Found {len(results)} account(s) with email: {email_to_find}")
        for row in results:
            print(f"  - User ID: {row['PartitionKey']}")
            print(f"  - Email: {row.get('email', 'N/A')}")
            print(f"  - Name: {row.get('name', 'N/A')}")
            print(f"  - Plan Status: {row.get('plan_status', 'N/A')}")
            print(f"  - Has Password Hash: {'password_hash' in row and bool(row['password_hash'])}")
    else:
        print(f"✗ No account found with email: {email_to_find}")
except Exception as e:
    print(f"Error querying Azure: {str(e)}")
