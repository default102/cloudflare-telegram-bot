import asyncio
from cloudflare import Cloudflare
from bot.config import settings

class CloudflareWrapper:
    def __init__(self):
        # v4 SDK automatically reads CLOUDFLARE_API_TOKEN env var if not passed,
        # but we pass it explicitly from our settings.
        self.client = Cloudflare(api_token=settings.cf_api_token)

    async def get_zones(self):
        # v4: client.zones.list()
        # Returns a SyncV4PagePagination[Zone], we convert to list
        # We run synchronous SDK calls in a separate thread to not block async loop
        return await asyncio.to_thread(lambda: list(self.client.zones.list()))

    async def get_dns_records(self, zone_id):
        # v4: client.dns.records.list(zone_id=...)
        return await asyncio.to_thread(lambda: list(self.client.dns.records.list(zone_id=zone_id)))

    async def get_dns_record_details(self, zone_id, record_id):
        # v4: client.dns.records.get(dns_record_id=..., zone_id=...)
        return await asyncio.to_thread(
            self.client.dns.records.get, 
            dns_record_id=record_id, 
            zone_id=zone_id
        )

    async def create_dns_record(self, zone_id, data):
        # v4: client.dns.records.create(zone_id=..., **data)
        # data needs to match RecordCreateParams
        return await asyncio.to_thread(
            self.client.dns.records.create,
            zone_id=zone_id,
            type=data['type'],
            name=data['name'],
            content=data['content'],
            proxied=data['proxied'],
            ttl=1 # Automatic
        )

    async def update_dns_record(self, zone_id, record_id, data):
        # v4: client.dns.records.edit(dns_record_id=..., zone_id=..., **data)
        return await asyncio.to_thread(
            self.client.dns.records.edit,
            dns_record_id=record_id,
            zone_id=zone_id,
            type=data['type'],
            name=data['name'],
            content=data['content'],
            proxied=data['proxied'],
            ttl=data.get('ttl', 1)
        )

    async def delete_dns_record(self, zone_id, record_id):
        # v4: client.dns.records.delete(dns_record_id=..., zone_id=...)
        return await asyncio.to_thread(
            self.client.dns.records.delete,
            dns_record_id=record_id,
            zone_id=zone_id
        )

cf = CloudflareWrapper()