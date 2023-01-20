import dataclasses


@dataclasses.dataclass
class Server:
    ip: str
    mac: str
    switch_port: int
