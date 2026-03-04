# ruff: noqa
import asyncio
import os

from app.sources.client.microsoft.microsoft import GraphMode, MSGraphClient, MSGraphClientWithClientIdSecretConfig
from app.sources.external.microsoft.one_note.one_note import OneNoteDataSource, OneNoteResponse

async def main():
    tenant_id = os.getenv("OUTLOOK_CLIENT_TENANT_ID")
    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    client_secret = os.getenv("OUTLOOK_CLIENT_SECRET")
    if not tenant_id or not client_id or not client_secret:
        raise Exception("OUTLOOK_CLIENT_TENANT_ID, OUTLOOK_CLIENT_ID, and OUTLOOK_CLIENT_SECRET must be set")

    # testing for enterprise account
    client: MSGraphClient = MSGraphClient.build_with_config(
        MSGraphClientWithClientIdSecretConfig(client_id, client_secret, tenant_id), 
        mode=GraphMode.APP)
    print(client)
    print("****************************")
    one_note_data_source: OneNoteDataSource = OneNoteDataSource(client)
    print("one_note_data_source:", one_note_data_source)
    print("Getting drive...")
    print("****************************")
    user_id_or_upn = os.getenv("USER_ID_OR_UPN")
    if not user_id_or_upn:
        raise Exception("USER_ID_OR_UPN must be set")
    response: OneNoteResponse = await one_note_data_source.users_get_onenote(user_id=user_id_or_upn)
    print(response.data)
    print(response.error)
    print(response.success)

    

if __name__ == "__main__":
    asyncio.run(main())


# Step 1: Collect Required Inputs
# Ask the user to provide:
# The date until which recurring events ending should be fetched.
# The new end date to extend those events to.
# Do not ask any additional questions after receiving these inputs.

# Step 2: Fetch Recurring Events
# Fetch all recurring Outlook events that are scheduled to end on or before the provided fetch date.

# Step 3: Retrieve Holidays
# Search and retrieve all holiday dates from the specified Confluence page. page -  "Holidays 2026"

# Step 4: Update Events
# Search each fetched recurring event by name and update its end date to the new end date provided by the user.

# Step 5: Remove Holiday and Weekend Occurrences
# Delete all occurrences of the updated events that fall on:
# Any retrieved holiday date
# Saturday
# Sunday
# Use the delete recurring event occurrence tool for each applicable date.

# Execution Rules

# Do not request confirmation after collecting the required inputs.
# Extend all fetched recurring events without asking the user to select specific ones.
# Always remove both Saturday and Sunday occurrences along with holiday occurrences.
# After execution, provide a concise summary of actions performed, including updated events and removed instances.