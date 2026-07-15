from znn.api.client import get_api_client


class StatsApi:
    def __init__(self, ws_client=None):
        self.ws_client = get_api_client(ws_client)

    async def os_info(self):
        """Get OS info of the connected node."""
        return await self.ws_client.send_request("stats.osInfo", [])

    async def process_info(self):
        """Get current version of node and commit hash."""
        return await self.ws_client.send_request("stats.processInfo", [])

    async def network_info(self):
        """Get info of connected peers to the network."""
        return await self.ws_client.send_request("stats.networkInfo", [])

    async def sync_info(self):
        return await self.ws_client.send_request("stats.syncInfo", [])
