import os
import asyncio
from dotenv import load_dotenv
from firecrawl import FirecrawlApp


class FirecrawlAPI:
    """
    Concrete class for interactions with the Firecrawl API.
    """

    def __init__(self, api_key: str = None, api_url: str = None):
        """
        Initializes the Firecrawl API object.

        Args:
            api_key (str, optional): The API key as a string or a path to a file containing the API key.
                If not provided, it will be loaded from the environment variable FIRECRAWL_KEY.
            api_url (str, optional): The base URL for the Firecrawl API.
                If not provided, it will be loaded from the environment variable FIRECRAWL_BASE_URL.
        """
        # Load API key from a file if the provided key is a filepath.
        if api_key and os.path.isfile(api_key):
            with open(api_key, "r") as f:
                self.api_key = f.read().strip()
        elif api_key:
            self.api_key = api_key
        else:
            load_dotenv()
            self.api_key = os.environ.get("FIRECRAWL_KEY")

        if not self.api_key:
            raise ValueError(
                "No valid Firecrawl API key found. Provide it as a string, file path, "
                "or set FIRECRAWL_KEY in the environment."
            )

        # Load the API URL from the argument or the environment.
        self.api_url = api_url or os.environ.get("FIRECRAWL_BASE_URL")

        # Initialize the Firecrawl SDK client.
        self.app = FirecrawlApp(api_key=self.api_key, api_url=self.api_url)

    async def search(self, query: str, timeout: int = 15, limit: int = 5) -> dict:
        """
        Performs a search using the Firecrawl SDK asynchronously.

        Args:
            query (str): The search query.
            timeout (int, optional): Timeout in milliseconds for the API call. Defaults to 15000.
            limit (int, optional): Maximum number of results to return. (Currently not used by the SDK call)

        Returns:
            dict: A dictionary with a "data" key containing the search results.
        """
        try:
            loop = asyncio.get_event_loop()
            # Run the synchronous SDK call in a thread pool
            response = await loop.run_in_executor(
                None, lambda: self.app.search(query=query)
            )
            # Process various response formats from the SDK
            if isinstance(response, dict) and "data" in response:
                return response
            elif isinstance(response, dict) and "success" in response:
                return {"data": response.get("data", [])}
            elif isinstance(response, list):
                formatted_data = []
                for item in response:
                    if isinstance(item, dict):
                        formatted_data.append(item)
                    else:
                        formatted_data.append(
                            {
                                "url": getattr(item, "url", ""),
                                "markdown": getattr(item, "markdown", "")
                                or getattr(item, "content", ""),
                                "title": getattr(item, "title", "")
                                or getattr(item, "metadata", {}).get("title", ""),
                            }
                        )
                return {"data": formatted_data}
            else:
                print(f"Unexpected response format from Firecrawl: {type(response)}")
                return {"data": []}
        except Exception as e:
            # If the error indicates a rate-limit (429), re-raise it for the caller to handle.
            if "429" in str(e):
                print(f"Rate limit error for query. Retrying in {timeout} seconds...")
                await asyncio.sleep(timeout)
                raise
            print(f"Error searching with Firecrawl: {e}")
            return {"data": []}
