# Sticky load balancing switch

This project is a Mininet simulation of a network with load balancing capabilities using OpenFlow. It consists of the following components:

* `swtich/topology.py`: This script defines the Mininet topology for the simulation. It creates a virtual network with multiple hosts and switches, and configures the switches to use OpenFlow for load balancing.

* `switch/settings.py`: This script contains various settings that can be used to configure the simulation, such as the number of servers.

* `switch/load_balancing_switch.py`: This script is an example of a Ryu controller that can be used to manage the virtual network created by the topology.py

## Dependencies

* Cloned repository `git clone https://github.com/nekeal/openflow-sticky-loadbalancer.git`
* `python3.9` - it was not tested for other Python versions, but it might work
* `mininet` and `openvswitch-switch` system packages -> `apt install mininet openvswitch-switch`
* python requirements - inside the root of the repository execute `pip install -r requirements.txt`

## Usage
Enter the switch directory inside the repository.

1. Run the openflow controller `ryu-manager load_balancing_switch.py`
2. Run the mininet topology `sudo python topology.py`
3. In the mininet CLI verify connectivity between all hosts `pingall`
4. Now you can use `curl` against virtual ip address `192.168.0.100` from any pc i.e. `pc1 curl 192.168.0.8080`.
   You will see response from the randomly chosen server (i.e `Response: server2`). From now on every packet to the virtual address from pc1 is
   switched to `http2` host.

## Topology
The StickyLoadBalancer class is a custom Mininet topology that defines a virtual network with the following components:

* 3 hosts named `pc1`, `pc2` and `pc3` with IP addresses `192.168.0.104-106/24`, 
and MAC addresses `aa:aa:aa:aa:aa:01-03`.
* A switch named `s1`.
* A list of HTTP servers defined in `settings.py` file. Each server is represented as a host with IP addresses "192.168.0.1" - "192.168.0.n" and MAC addresses "00:00:00:00:00:01" - "00:00:00:00:00:n" respectively,
where n is the number of servers. 

The topology connects all the hosts and servers to the switch. 
The `run_topology` function is used to start the Mininet simulation, it takes the IP address of the controller as an argument,
creates an instance of the StickyLoadBalancer topology and starts the Mininet network with the OVSSwitch, and it connects 
to the remote controller at the IP address passed on port `6633`.

It starts the servers by running a python script on the servers and starts the mininet CLI for the user to interact with the topology. Once the user exits the CLI, the Mininet network is stopped.


## Customization

In the `settings.py` file you can customize the number and way how http servers are generated.

In the `topology.py` you can modify overall topology used in this project i.e. number of PCs. 

`ClientRepository` in the `repositories.py` file stores mapping between client's IP and assigned server.
It's also responsible for choosing random server. 

