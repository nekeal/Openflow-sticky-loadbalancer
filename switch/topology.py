import sys

import settings
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


class StickyLoadBalancer(Topo):
    """
    SDN sticky loadbalancer topology
    It consists of 3 hosts pc[1-3] and list of servers defined in settings.py
    """

    def build(self):

        # Add hosts and switches
        pc1 = self.addHost("pc1", ip="192.168.0.104/24", mac="aa:aa:aa:aa:aa:01")
        pc2 = self.addHost("pc2", ip="192.168.0.105/24", mac="aa:aa:aa:aa:aa:02")
        pc3 = self.addHost("pc3", ip="192.168.0.106/24", mac="aa:aa:aa:aa:aa:03")
        switch = self.addSwitch("s1")

        for i, server in enumerate(settings.SERVERS, 1):
            host = self.addHost(
                f"http{i}",
                ip=f"192.168.0.{i+1}",
                mac=f"00:00:00:00:00:{hex(i+1)[2:].zfill(2)}",
            )
            self.addLink(host, switch, 0, i)
        self.addLink(pc1, switch)
        self.addLink(pc2, switch)
        self.addLink(pc3, switch)


def run_topology(controller_ip):
    topology = StickyLoadBalancer()

    net = Mininet(
        topo=topology,
        switch=OVSSwitch,
        autoSetMacs=True,
        controller=RemoteController(name="c1", ip=controller_ip, port=6633),
    )
    net.start()

    for i, server in enumerate(settings.SERVERS, 1):  # startup script for http servers
        net.get(f"http{i}").cmd(f"python3 http_server/run_server.py server{i} &")

    CLI(net)
    net.stop()


topos = {"sticky": run_topology}


if __name__ == "__main__":
    """
    Usage: sudo python topology.py <ip-of-a-controller=127.0.0.1>
    You probably want to change the default when running mininet on another machine
    """
    controller_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    run_topology(controller_ip)
