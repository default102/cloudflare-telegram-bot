import asyncio
import CloudFlare
from bot.config import settings

class CloudflareWrapper:
    def __init__(self):
        self.cf = CloudFlare.CloudFlare(token=settings.cf_api_token)

    async def get_zones(self):
        return await asyncio.to_thread(self.cf.zones.get)

    async def get_dns_records(self, zone_id):
        return await asyncio.to_thread(self.cf.zones.dns_records.get, zone_id)

    async def get_dns_record_details(self, zone_id, record_id):
        return await asyncio.to_thread(self.cf.zones.dns_records.get, zone_id, record_id)

    async def create_dns_record(self, zone_id, data):
        # data format: {'name': 'test.example.com', 'type': 'A', 'content': '1.2.3.4', 'proxied': False}
        return await asyncio.to_thread(self.cf.zones.dns_records.post, zone_id, data=data)

    async def update_dns_record(self, zone_id, record_id, data):
        return await asyncio.to_thread(self.cf.zones.dns_records.put, zone_id, record_id, data=data)

    async def delete_dns_record(self, zone_id, record_id):
        return await asyncio.to_thread(self.cf.zones.dns_records.delete, zone_id, record_id)

cf = CloudflareWrapper()
