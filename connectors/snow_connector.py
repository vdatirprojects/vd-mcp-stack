import logging
import httpx
import urllib.parse
import os
import dotenv
import base64
from typing import List, Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from base.logging import get_logger
logger = get_logger(__name__)



# load env variables 
dotenv.load_dotenv()

user_id = os.getenv("SNOW_USER_ID","")
password = os.getenv("SNOW_PASSWORD","")
snow_server = os.getenv('SNOW_SERVER', '')

# Configure SSL verification for ServiceNow
verify_ssl = True

if not user_id or not password:
    raise RuntimeError("SNOW_USER_ID or SNOW_PASSWORD environment variables are not set")


auth_header = f"{user_id}:{password}"
encoded_auth = base64.b64encode(auth_header.encode("utf-8")).decode("ascii")

headers = {
    "Accept": "application/json",
    "Authorization": f"Basic {encoded_auth}",
}



# aggregate function
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def aggregate(table_name: str, sysparm_group_by:str, sysparm_avg_fields=None, sysparm_max_fields=None, sysparm_min_fields=None, sysparm_sum_fields=None,  sysparm_query:Optional[str] = None, sysparm_display_value:str = "true", sysparm_count:bool = True):

    query_params = {
        "sysparm_count": sysparm_count,
        "sysparm_display_value": sysparm_display_value,
        "sysparm_group_by": sysparm_group_by
    }

    if not sysparm_query is None:
        # url encode the sysparm_query
        query_params['sysparm_query'] = urllib.parse.quote(sysparm_query)

    if not sysparm_avg_fields is None:
        query_params["sysparm_avg_fields"] = sysparm_avg_fields

    if not sysparm_max_fields is None:
        query_params["sysparm_max_fields"] = sysparm_max_fields

    if not sysparm_min_fields is None:
        query_params["sysparm_min_fields"] = sysparm_min_fields

    if not sysparm_sum_fields is None:
        query_params["sysparm_sum_fields"] = sysparm_sum_fields

    url = f"{os.getenv('SNOW_SERVER')}/api/now/stats/{table_name}?" + '&'.join(f"{key}={value}" for key, value in query_params.items())

    async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            print('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.text)
            return None

        return response.json()
    

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def get_table(table_name, sysparm_query:Optional[str]=None, sysparm_limit:Optional[int] = 200):
    query_params = {}
    if not sysparm_limit is None:
        sysparm_limit = int(sysparm_limit)
        query_params['sysparm_limit'] = sysparm_limit
    if not sysparm_query is None:
        # url encode the sysparm_query
        query_params['sysparm_query'] = urllib.parse.quote(sysparm_query)


    url = f"{os.getenv('SNOW_SERVER')}/api/now/table/{table_name}?" + '&'.join(f"{key}={value}" for key, value in query_params.items())

    logging.debug(f"Fetching table data from: {url}")

    async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            print('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.text)
            return None

        return response.json()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def get_kb_attachment(article_folder, attachment):
    attachment_url = f"{os.getenv('SNOW_SERVER')}/api/now/attachment/{attachment['sys_id']}/file"

    async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
        attachment_response = await client.get(attachment_url, headers=headers)

        if attachment_response.status_code == 200:
            attachment_path = f"{article_folder}/{attachment['file_name']}"
            os.makedirs(os.path.dirname(attachment_path), exist_ok=True)
            with open(attachment_path, 'wb') as f:
                f.write(attachment_response.content)
            logging.info(f"Downloaded attachment: {attachment['file_name']} to {attachment_path}")
            return attachment_path
        else:
            logging.error(f"Failed to download attachment: {attachment['file_name']} - Status Code: {attachment_response.status_code}")

if __name__ == "__main__":
    import asyncio
    import dotenv
    dotenv.load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    logger = logging.getLogger("snow_api")

    async def main():
        logging.info(f"Connecting to server {os.getenv('SNOW_SERVER')}")
        try:
            result = await aggregate("incident", "priority", sysparm_query="priority>1")
            print(result)
        except Exception as e:
            logging.error(f"Example aggregate call failed: {e}")

    asyncio.run(main())
