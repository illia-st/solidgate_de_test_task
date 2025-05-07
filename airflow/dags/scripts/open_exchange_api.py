import requests
from typing import Optional, Dict, Any


class OpenExchangeRatesAPI:
    BASE_URL = "https://openexchangerates.org/api"

    def __init__(self, app_id: str):
        if not app_id:
            raise ValueError("API key (app_id) is required.")
        self.app_id = app_id

    def get_latest_rates(
        self, base: Optional[str] = "EUR", callback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch the latest exchange rates.

        :param base: Optional base currency (e.g., 'GBP')
        :param callback: Optional JSONP callback function name
        :return: Parsed JSON response with exchange rates
        """
        url = f"{self.BASE_URL}/latest.json"
        params = {"app_id": self.app_id}
        if base:
            params["base"] = base
        if callback:
            params["callback"] = callback

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_currencies(self) -> Dict[str, str]:
        """
        Get the list of available currency codes and their names.

        :return: Dictionary mapping currency codes to names
        """
        url = f"{self.BASE_URL}/currencies.json"
        params = {"app_id": self.app_id}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
