import re

def parseRanges(config):
    config = config.splitlines()
    vlan_list = []

    for line in config:
        if line.startswith("vlan ") and ("-" in line or "," in line):
            # Remove "vlan " prefix
            vlan_range_str = line.removeprefix("vlan ")

            # This is a vlan with a range
            for vlan_part in vlan_range_str.split(","):
                if "-" in vlan_part:
                    vlan_range = vlan_part.split("-")
                    vlan_list += [str(i) for i in range(int(vlan_range[0]), int(vlan_range[-1]) + 1)]
                else:
                    vlan_list.append(str(vlan_part))

            # break after first vlan line
            break

    return vlan_list

def removeOldLines(config, interfaces, vlans):
    config = config.splitlines()
    new_config = []

    # Remove lines that will be filled in by this plugin
    delete_section = False
    found_vlanrange_line = False
    for line in config:
        if line.startswith("!"):
            # skip commands
            continue

        if line == "" and delete_section:
            # Skip empty lines if deleting
            continue

        if not line.startswith(" "):
            # This is a new section
            delete_section = False

        if line.startswith("interface breakout "):
            # Existing breakout config, get port
            match = re.search(r"port (\d+)", line)
            if match:
                port_num = match.group(1)
                object_name = f"Ethernet1/{port_num}"
                if object_name in interfaces:
                    continue

        if line.startswith("interface "):
            # This is an interface config

            # Find the object name
            object_name = line.removeprefix("interface ")
            if not object_name.startswith("Ethernet") and not object_name.startswith("port-channel"):
                delete_section = False;
                new_config.append(line)
                continue

            # Check if object is configured
            if object_name.count("/") > 1:
                # this is a breakout
                object_name = object_name[:object_name.rfind("/")]

            if object_name in interfaces:
                if "managed" in interfaces[object_name] and interfaces[object_name]["managed"]:
                    delete_section = False
                    new_config.append(line)
                    continue
                else:
                    delete_section = True
                    continue
            else:
                new_config.append(line)
                delete_section = False
                continue

        if line.startswith("vlan "):
            if not found_vlanrange_line:
                # Skip vlan range line
                found_vlanrange_line = True
                continue

            # This is a VLAN config
            object_name = int(line.removeprefix("vlan "))
            if object_name in vlans:
                if "managed" in vlans[object_name] and vlans[object_name]["managed"]:
                    delete_section = False
                    new_config.append(line)
                    continue
                else:
                    delete_section = True
                    continue
            else:
                delete_section = True
                continue

        if not delete_section:
            new_config.append(line)

    return new_config

def generateVLANConfig(vlans):
    config = []
    for id,fields in vlans.items():
        if "managed" in fields and fields["managed"]:
            continue

        config.append("")  # Newline
        config.append(f"vlan {str(id)}")
        config.append(f"  name {fields["name"]}")

    return config

def generateINTFConfig(interfaces):
    def getLAGMembers(fields):
        members = []
        if "lag-members" in fields:
            members += fields["lag-members"]

        if "lacp-members-active" in fields:
            members += fields["lacp-members-active"]

        if "lacp-members-passive" in fields:
            members += fields["lacp-members-passive"]

        outlist = []
        for member in members:
            outlist.append(f"interface {member}")

        return outlist

    config_dict = {}

    config = []
    for intf,fields in interfaces.items():
        intf_num = intf.split(" ")[-1]

        # "fanout" field
        if "fanout" in fields:
            fanout_fields = fields["fanout"]
            nxos_mode_str = ""
            if fanout_fields["mode"] == "quad":
                nxos_mode_str = "4x"
            elif fanout_fields["mode"] == "dual":
                nxos_mode_str = "2x"
            elif fanout_fields["mode"] == "single":
                nxos_mode_str = "1x"

            intf_port = intf_num.split("/")[-1]
            nxos_fanout_str = f"{fanout_fields["speed"]}-{nxos_mode_str}"
            config_dict[f"interface breakout module 1 port {intf_port} map {nxos_fanout_str}"] = []
            continue

        intf_cfg_label = intf
        dict_key = f"interface {intf_cfg_label}"
        if dict_key not in config_dict:
            config_dict[dict_key] = []

        is_portchannel = intf.startswith("port-channel")
        if is_portchannel:
            intf_num = intf[len("port-channel"):]

        # "description" field
        if "description" in fields:
            config_dict[dict_key].append(f"description {fields["description"]}")

        # "enabled" field
        if "enabled" in fields:
            if fields["enabled"]:
                config_dict[dict_key].append("no shutdown")
            else:
                config_dict[dict_key].append("shutdown")

        # "mtu" field
        if "mtu" in fields:
            config_dict[dict_key].append(f"mtu {fields["mtu"]}")

            if is_portchannel:
                for member_port in getLAGMembers(fields):
                    if member_port not in config_dict:
                        config_dict[member_port] = []

                    config_dict[member_port].append(f"mtu {fields["mtu"]}")

        # "autoneg" field
        if "autoneg" in fields:
            if fields["autoneg"]:
                config_dict[dict_key].append("speed auto")
            else:
                config_dict[dict_key].append("no negotiate auto")

        # "speed" field
        if "speed" in fields:
            config_dict[dict_key].append(f"speed {fields["speed"]}")

        # "fec" field
        if "fec" in fields:
            if fields["fec"]:
                config_dict[dict_key].append("fec auto")
            else:
                config_dict[dict_key].append("fec off")

        # Set to L3 mode if needed
        is_l3 = "ip4" in fields or "ip6" in fields
        if is_l3:
            config_dict[dict_key].append("no switchport")

        # "ip4" field
        if "ip4" in fields:
            config_dict[dict_key].append(f"ip address {fields["ip4"]}")

        # "ip6" field
        if "ip6" in fields:
            config_dict[dict_key].append(f"ipv6 address {fields["ip6"]}")

        # "stp" field
        if "stp" in fields:
            stp_fields = fields["stp"]
            if "edgeport" in stp_fields and stp_fields["edgeport"]:
                edge_str = "spanning-tree port type edge"
                if "bpduguard" in stp_fields and stp_fields["bpduguard"]:
                    edge_str += " bpduguard"

                config_dict[dict_key].append(edge_str)

            if "rootguard" in stp_fields and stp_fields["rootguard"] and not is_l3:
                config_dict[dict_key].append("spanning-tree guard root")

            if "loopguard" in stp_fields and stp_fields["loopguard"]:
                if is_l3:
                    config_dict[dict_key].append("spanning-tree loopguard")
                else:
                    config_dict[dict_key].append("spanning-tree guard loop")

        # "portmode" field
        if "portmode" in fields:
            portmode_str = ""
            if fields["portmode"] == "access":
                portmode_str = "switchport mode access"
            elif fields["portmode"] == "trunk" or fields["portmode"] == "hybrid":
                portmode_str = "switchport mode trunk"

            config_dict[dict_key].append(portmode_str)

            if is_portchannel:
                for member_port in getLAGMembers(fields):
                    if member_port not in config_dict:
                        config_dict[member_port] = []

                    config_dict[member_port].append(portmode_str)

        # "tagged" field
        if "tagged" in fields:
            allowed_vl_string = ",".join(list(map(str, fields["tagged"])))
            tagged_str = f"switchport trunk allowed vlan {allowed_vl_string}"
            config_dict[dict_key].append(tagged_str)

            if is_portchannel:
                for member_port in getLAGMembers(fields):
                    if member_port not in config_dict:
                        config_dict[member_port] = []

                    config_dict[member_port].append(tagged_str)

        # "untagged" field
        if "untagged" in fields:
            untagged_str = ""
            if fields["portmode"] == "hybrid":
                untagged_str = f"switchport trunk native vlan {fields["untagged"]}"
            else:
                untagged_str = f"switchport access vlan {fields["untagged"]}"

            config_dict[dict_key].append(untagged_str)

            if is_portchannel:
                for member_port in getLAGMembers(fields):
                    if member_port not in config_dict:
                        config_dict[member_port] = []

                    config_dict[member_port].append(untagged_str)

        # "lag-members" field
        if "lag-members" in fields:
            for member in fields["lag-members"]:
                member = f"interface {member}"
                if member not in config_dict:
                    config_dict[member] = []

                config_dict[member].append(f"channel-group {intf_num} mode on")

        # "lacp-members-active" field
        if "lacp-members-active" in fields:
            for member in fields["lacp-members-active"]:
                member = f"interface {member}"
                if member not in config_dict:
                    config_dict[member] = []

                config_dict[member].append(f"channel-group {intf_num} mode active")

        # "lacp-members-passive" field
        if "lacp-members-passive" in fields:
            for member in fields["lacp-members-passive"]:
                member = f"interface {member}"
                if member not in config_dict:
                    config_dict[member] = []

                config_dict[member].append(f"channel-group {intf_num} mode passive")

        # "lacp-rate" field
        if "lacp-rate" in fields:
            for member in getLAGMembers(fields):
                if member not in config_dict:
                    config_dict[member] = []

                if fields["lacp-rate"] == "fast":
                    config_dict[member].append("lacp rate fast")
                else:
                    config_dict[member].append("lacp rate normal")

        # "mlag" field
        if "mlag" in fields:
            if fields["mlag"]:
                config_dict[member_port].append(f"vpc {fields["mlag"]}")

    for key,lines in config_dict.items():
        config.append("")
        config.append(key)
        for line in lines:
            config.append(f"  {line}")

    return config

def NXOS_GETCONFIG(running_config, interfaces, vlans):
    parsedVLANs = parseRanges(running_config)
    outputVLANs = []

    for vlan,fields in vlans.items():
        if "managed" in fields and fields["managed"]:
            if str(vlan) in parsedVLANs:
                outputVLANs.append(str(vlan))

            continue

        outputVLANs.append(str(vlan))

    new_config = removeOldLines(running_config, interfaces, vlans)

    # Add default vlan
    outputVLANs.insert(0, "1")

    vlan_cfg_str = "vlan " + ",".join(outputVLANs)
    new_config.append("")
    new_config.append(vlan_cfg_str)
    new_config += generateVLANConfig(vlans)

    new_config += generateINTFConfig(interfaces)

    out_config = "\n".join(new_config)
    return out_config

class FilterModule(object):
    def filters(self):
        return {
            "NXOS_GETCONFIG": NXOS_GETCONFIG
        }
