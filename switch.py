#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

MULTICAST_MAC = b'\x01\x80\xc2\x00\x00\x00'

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    global own_bridge_id, root_bridge_id, root_path_cost, root_port, interfaces, VLAN_table
    while True:
        if own_bridge_id == root_bridge_id:
            for i in interfaces:
                if VLAN_table[i] == -1:
                    send_bpdu(i, root_bridge_id, root_path_cost, own_bridge_id)
        time.sleep(1)

def is_unicast(mac_address):
    return mac_address != b'\xff\xff\xff\xff\xff\xff'

def is_broadcast(dest_mac):
    return dest_mac == b'\xff\xff\xff\xff\xff\xff'

def read_config(switch_id):
    global VLAN_table

    file_name = f"configs/switch{switch_id}.cfg"
    
    with open(file_name, 'r') as file:
        lines = file.readlines()[0:]

        p = int(lines[0].strip())
        
        for i, line in enumerate(lines [1:]):
            
            line = line.strip()
            if line.endswith('T'):
                VLAN_table[i] = -1
            else:
                VLAN_table[i] = int(line[-1])
    return p

def broadcast(interface_list, interface, length, data, vlan):
    global MAC_table, VLAN_table, STATE_table
    for i in interface_list:
        if i != interface and STATE_table[i] == 1:
            if VLAN_table[i] == vlan:
                send_to_link(i, length, data)
            else:
                tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
                send_to_link(i, length + 4, tagged_frame)

def send_bpdu(interface, root_bridge_id, root_path_cost, own_bridge_id):
    global interfaces
    dst_mac = 0x0180C2000000
    mac_cast = struct.pack('!6s', dst_mac.to_bytes(6, byteorder='big'))
    src_mac = get_switch_mac()
    llc_length = struct.pack('!H', 0)
    byte1 = 0x42
    byte2 = 0x42
    byte3 = 0x03
    llc_heather = struct.pack('!3s', byte1.to_bytes(1, byteorder='big') + byte2.to_bytes(1, byteorder='big') + byte3.to_bytes(1, byteorder='big'))
    bpdu_header = struct.pack('!I', 0)
    root_bid = struct.pack('!q', root_bridge_id)
    cost_path = struct.pack('!I', root_path_cost)
    own_bid = struct.pack('!q', own_bridge_id)
    data = mac_cast + src_mac + llc_length + llc_heather + bpdu_header + root_bid + cost_path + own_bid
    send_to_link(interface, len(data), data)

def init_bpdu(priority_value):
    global VLAN_table
    STATE_table = {}
    for i in interfaces:
        if VLAN_table[i] == -1:
            STATE_table[i] = 0
    own_bridge_id = int(priority_value)
    root_bridge_id = int(priority_value)
    root_path_cost = 0
    if own_bridge_id == root_bridge_id:
        for i in interfaces:
            STATE_table[i] = 1
    root_port = None
    return STATE_table, own_bridge_id, root_bridge_id, root_path_cost, root_port

def get_bpdu(data):
    rbi = int.from_bytes(data[21:29], byteorder='big')
    rpc = int.from_bytes(data[29:33], byteorder='big')
    obi = int.from_bytes(data[33:41], byteorder='big')
    return rbi, rpc, obi

def check_if_i_am_root(own_bid, root_bid):
    am_i_root = False
    if own_bid == root_bid:
        am_i_root = True
    return am_i_root

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    global interfaces, own_bridge_id, root_bridge_id, root_path_cost, root_port, MAC_table, VLAN_table, STATE_table
    switch_id = sys.argv[1]

    MAC_table = {}
    VLAN_table = {}

    priority_value = read_config(switch_id)

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    STATE_table, own_bridge_id, root_bridge_id, root_path_cost, root_port = init_bpdu(priority_value)

    print("[INFO] Own bridge id", own_bridge_id)

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    while True:
        interface, data, length = recv_from_any_link()

        if data[0:6] == MULTICAST_MAC:
            root_bridge_id_rec, sender_path_cost, sender_bridge_id = get_bpdu(data)

            am_i_root = check_if_i_am_root(own_bridge_id, root_bridge_id)

            if root_bridge_id_rec < root_bridge_id:
                root_bridge_id = root_bridge_id_rec
                root_path_cost = sender_path_cost + 10
                root_port = interface
                if am_i_root:
                    for i in interfaces:
                        if (i != root_port) and (VLAN_table[i] == -1):
                            STATE_table[i] = 0
                            am_i_root = False
                if STATE_table[root_port] == 0:
                    STATE_table[root_port] = 1
                for i in interfaces:
                    if (i != root_port and VLAN_table[i] == -1):
                        send_bpdu(i, root_bridge_id, root_path_cost, own_bridge_id)
            elif root_bridge_id_rec == root_bridge_id:
                if (interface == root_port) and (sender_path_cost + 10 < root_path_cost):
                    root_path_cost = sender_path_cost + 10
                elif (interface != root_port):
                    if sender_path_cost > root_path_cost:
                        if STATE_table[interface] == 0:
                            STATE_table[interface] = 1 
            elif sender_bridge_id == own_bridge_id:
                STATE_table[interface] = 0
            else:
                continue
            if am_i_root:
                for i in interfaces:
                    STATE_table[i] = 1
            continue

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        print(f'Destination MAC: {dest_mac}')
        print(f'Source MAC: {src_mac}')
        print(f'EtherType: {ethertype}')

        print("Received frame of size {} on interface {}".format(length, interface), flush=True)
            
        # TODO: Implement forwarding with learning

        if vlan_id == -1:
            vlan = VLAN_table[interface]
        else:
            vlan = vlan_id
            length = length - 4
            data = data[0:12] + data[16:]

        if src_mac not in MAC_table:
            MAC_table[src_mac] = interface

        if is_unicast(dest_mac):
            if dest_mac in MAC_table:
                if VLAN_table[MAC_table[dest_mac]] == vlan:
                    send_to_link(MAC_table[dest_mac], length, data)
                else:
                    tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
                    send_to_link(MAC_table[dest_mac], length + 4, tagged_frame)
            else:
                broadcast(interfaces, interface, length, data, vlan)
        if is_broadcast(dest_mac):
            broadcast(interfaces, interface, length, data, vlan)

if __name__ == "__main__":
    main()
