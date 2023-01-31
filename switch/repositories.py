import random
from collections import defaultdict
from typing import Optional

import settings
from entities import Server


class MACPortRepository:
    def __init__(self):
        self._mapping = defaultdict(dict)

    def add(self, switch_id: str, mac: str, port: int):
        self._mapping[switch_id][mac] = port

    def get(self, switch_id: str, mac: str) -> int:
        return self._mapping.get(switch_id).get(mac)

    def __contains__(self, item: tuple[str, str]) -> bool:
        dpid, mac = item
        return mac in self._mapping[dpid]


class ClientRepository:
    def __init__(self):
        """
        _mapping stores the mapping between client ip and assigned server ip
        """
        self._mapping: dict[str, Server] = {}
        self.servers: list[Server] = settings.SERVERS

    def add(self, client_ip: str, server: Server):
        self._mapping[client_ip] = server

    def get(self, client_ip: str) -> Server:
        """
        :param client_ip:
        :return: server assigned to the client's IP. Otherwise, random server is chosen.
        """
        if not (assigned_server := self._mapping.get(client_ip)):
            random_server = random.choice(self.servers)
            self.add(client_ip, random_server)
            return random_server
        return assigned_server

    def get_server_by_mac(self, mac: str) -> Optional[Server]:
        return next((server for server in self.servers if server.mac == mac), None)
