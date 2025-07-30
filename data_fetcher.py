import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

class ForexDataFetcher:
    def __init__(self, twelve_data_key=None, alpha_vantage_key=None):
        self.twelve_data_key = twelve_data_key or os.getenv("TWELVE_DATA_API_KEY")
        self.alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.session = aiohttp.ClientSession()

    async def fetch_data(self, symbol):
        # Placeholder for fetching data; implement your API calls here
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&apikey={self.twelve_data_key}"
        async with self.session.get(url) as response:
            return await response.json()

    async def close(self):
        await self.session.close()
