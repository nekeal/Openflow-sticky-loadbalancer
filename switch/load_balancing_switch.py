"""
An OpenFlow 1.3 load balancing switch.
"""
import sys

from repositories import ClientRepository, MACPortRepository
from ryu.base import app_manager
from ryu.cmd.manager import main
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, MAIN_DISPATCHER,
                                    set_ev_cls)
from ryu.lib.packet import arp, ether_types, ethernet, ipv4, packet
from ryu.lib.packet.ether_types import ETH_TYPE_IP
from ryu.ofproto import ofproto_v1_3


class StickLoadBalancingSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    VIRTUAL_IP = "192.168.0.100"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database = MACPortRepository()
        self.client_database = ClientRepository()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        !THIS IS REQUIRED FOR THE SWITCH TO WORK FOR OF >= 1.2!

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.

        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.install_flow(datapath, 0, match, actions)
        self.logger.info("Switch %s connected", datapath.id)

    @staticmethod
    def install_flow(datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        buffer_id = buffer_id or ofproto.OFP_NO_BUFFER
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            buffer_id=buffer_id,
            priority=priority,
            match=match,
            instructions=inst,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Basic packet_in handler
        :param ev: event object
        :return:
        """

        msg = ev.msg
        datapath = msg.datapath
        dpid = format(datapath.id, "d").zfill(16)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype in (
            ether_types.ETH_TYPE_LLDP,
            ether_types.ETH_TYPE_IPV6,
        ):  # ignore lldp and ipv6 packets for clarity
            return

        self.logger.info(
            "packet in %s %s %s %s %s", dpid, eth.src, in_port, eth.dst, msg.buffer_id
        )

        # add mac to the database
        self.database.add(dpid, eth.src, in_port)

        if (
            eth.ethertype == ether_types.ETH_TYPE_ARP
        ):  # handle arp request for the virtual IP
            arp_header = pkt.get_protocol(arp.arp)
            if (
                arp_header.opcode == arp.ARP_REQUEST
                and arp_header.dst_ip == self.VIRTUAL_IP
            ):
                self._handle_arp_request(
                    datapath, arp_header, in_port, ofproto, datapath.ofproto_parser
                )
                return

        if (
            eth.ethertype == ETH_TYPE_IP  # handle IP packets to the virtual IP
            and (ip_header := pkt.get_protocol(ipv4.ipv4)).dst == self.VIRTUAL_IP
        ):
            self._handle_ip_packet(
                datapath, in_port, ip_header, parser, eth.dst, eth.src
            )
            self.logger.info(
                "IP packet handled from %s to %s", ip_header.src, ip_header.dst
            )
            return

        out_port = self.database.get(dpid, eth.dst) or ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:  # install flow for know out_port
            extra_match = (  # match also on the destination ip address
                {"eth_type": ETH_TYPE_IP, "ipv4_dst": pkt.get_protocol(ipv4.ipv4).dst}
                if eth.ethertype == ETH_TYPE_IP
                else {"eth_type": eth.ethertype}
            )
            match = parser.OFPMatch(
                in_port=in_port, eth_dst=eth.dst, eth_src=eth.src, **extra_match
            )
            priority = 2 if "ipv4_dst" in match else 1
            self.install_flow(datapath, priority, match, actions, msg.buffer_id)
            if (
                msg.buffer_id != ofproto.OFP_NO_BUFFER
            ):  # if we have a valid buffer_id FlowMod message will send the packet
                return

        self.send_packet_out(actions, datapath, in_port, msg, ofproto, parser)

    @staticmethod
    def send_packet_out(actions, datapath, in_port, msg, ofproto, parser):
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    def _handle_arp_request(
        self, datapath, arp_header: arp.arp, in_port, ofproto, parser
    ):
        """
        Handle ARP request for the virtual IP
        :param datapath: switch datapath
        :param arp_header: header of the ARP request
        :param in_port: port on which the ARP request was received
        :param ofproto: ofproto instance
        :param parser: parser instance
        :return: None
        """
        self.logger.info(
            "ARP request client ip: %s, client mac: %s",
            arp_header.src_ip,
            arp_header.src_mac,
        )
        # Build an ARP reply packet using source IP and source MAC
        reply_packet = self.generate_arp_reply_packet(
            arp_header.src_ip, arp_header.src_mac
        )
        actions = [parser.OFPActionOutput(in_port)]
        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            in_port=ofproto.OFPP_ANY,
            data=reply_packet.data,
            actions=actions,
            buffer_id=ofproto.OFP_NO_BUFFER,
        )
        datapath.send_msg(packet_out)
        self.logger.info("Sent the ARP reply packet")
        return

    def generate_arp_reply_packet(self, dst_ip: str, dst_mac: str):
        """
        Generate an ARP reply packet
        :param dst_ip: ip of host who requested the arp reply
        :param dst_mac: mac of host who requested the arp reply
        :return: None
        """

        server = self.client_database.get(dst_ip)
        src_mac = server.mac
        self.logger.info("Selected server MAC: %s, IP %s", server.mac, server.ip)

        pkt = packet.Packet()
        pkt.add_protocol(
            ethernet.ethernet(
                dst=dst_mac, src=src_mac, ethertype=ether_types.ETH_TYPE_ARP
            )
        )
        pkt.add_protocol(
            arp.arp(
                opcode=arp.ARP_REPLY,
                src_mac=src_mac,
                src_ip=self.VIRTUAL_IP,
                dst_mac=dst_mac,
                dst_ip=dst_ip,
            )
        )
        pkt.serialize()
        return pkt

    def _handle_ip_packet(
        self, datapath, in_port, ip_header: ipv4.ipv4, parser, dst_mac, src_mac
    ):
        """Handles IP packets to the virtual IP"""

        server = self.client_database.get_server_by_mac(dst_mac)
        self.logger.info(
            "Selected server MAC: %s, IP %s, proto: %s",
            server.mac,
            server.ip,
            ip_header.proto,
        )

        match = parser.OFPMatch(
            in_port=in_port,
            eth_type=ETH_TYPE_IP,
            # ip_proto=ip_header.proto,
            ipv4_dst=self.VIRTUAL_IP,
        )

        actions = [
            parser.OFPActionSetField(ipv4_dst=server.ip),
            parser.OFPActionOutput(server.switch_port),
        ]

        self.install_flow(datapath, 10, match, actions)

        match = parser.OFPMatch(
            in_port=server.switch_port,
            eth_type=ETH_TYPE_IP,
            # ip_proto=ip_header.proto,
            ipv4_src=server.ip,
            eth_dst=src_mac,
        )
        actions = [
            parser.OFPActionSetField(ipv4_src=self.VIRTUAL_IP),
            parser.OFPActionOutput(in_port),
        ]

        self.install_flow(datapath, 10, match, actions)
        return True


if __name__ == "__main__":
    sys.argv.append(__name__)
    main()
