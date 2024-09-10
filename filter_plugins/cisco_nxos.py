import re


def getVLANList(config: str):
    """
    Parses vlan ranges in config files. For example, vlan 5-8,10,15-17 will return [5,6,7,8,10,15,16,17]

    :param config: The config string block to parse the VLAN block for
    :type config: str
    :return: A list of VLAN IDs
    :rtype: list
    """
    config = config.splitlines()
    vlan_list = []

    for line in config:
        if line.startswith("vlan "):
            # Remove "vlan " prefix
            vlan_range_str = line.removeprefix("vlan ")

            # This is a vlan with a range
            for vlan_part in vlan_range_str.split(","):
                if "-" in vlan_part:
                    vlan_first, vlan_last = vlan_part.split("-")
                    vlan_list += [
                        str(i) for i in range(int(vlan_first), int(vlan_last) + 1)
                    ]
                else:
                    vlan_list.append(str(vlan_part))

            # break after first vlan line (all vlans are on the first vlan line)
            break

    return vlan_list


def removeOldLines(config: str, interfaces: dict, vlans: dict):
    """
    This method will take a NXOS config block and remove all the lines that should be overwritten by the ansible generated config
    This includes any interface block defined in the config that is in the manifest, except those with "managed": true in the manifest

    Example:

    interface Ethernet1/33
        shutdown

    interface Ethernet1/34
        shutdown

    interface Ethernet1/35
        shutdown

    interface Ethernet1/36
        shutdown

    interface mgmt0
      vrf member management
      ip address 10.80.3.1/20
    icam monitor scale

    line console
    line vty
    boot nxos bootflash:/nxos64-cs.10.3.2.F.bin
    no system default switchport shutdown

    Output of this method will be:

    interface mgmt0
      vrf member management
      ip address 10.80.3.1/20
    icam monitor scale

    line console
    line vty
    boot nxos bootflash:/nxos64-cs.10.3.2.F.bin
    no system default switchport shutdown

    :param config: The NXOS config block to parse
    :type config: str
    :param interfaces: The interfaces manifest
    :type interfaces: dict
    :param vlans: The VLANs manifest
    :type vlans: dict
    :return: The existing running config without lines that are maintained by ansible manifest
    :rtype: str
    """
    config = config.splitlines()
    new_config = []

    # Remove lines that will be filled in by this plugin
    # When delete section is true lines will be deleted
    # The idea is that after a section is over (such as an interface block)
    # delete section will be reset to false and be put back to true only if
    # the next line is determined to be a section that should be deleted
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
            if match := re.search(r"port (\d+)", line):
                port_num = match.group(1)
                object_name = f"Ethernet1/{port_num}"
                if object_name in interfaces:
                    continue

        if line.startswith("interface "):
            # This is an interface config

            # Find the object name
            object_name = line.removeprefix("interface ")
            if (
                not object_name.startswith("Ethernet")
                and not object_name.startswith("port-channel")
                and not object_name.startswith("Vlan")
            ):
                # This allows things like management interfaces to pass through
                delete_section = False
                new_config.append(line)
                continue

            # Check if this is a managed interface, if so, don't remove the section
            if object_name in interfaces and interfaces[object_name].get("managed"):
                delete_section = False
                new_config.append(line)
                continue

            # Delete section
            delete_section = True
            continue

        if line.startswith("vlan "):
            if not found_vlanrange_line:
                # Skip vlan range line
                found_vlanrange_line = True
                continue

            # This is a VLAN config
            object_name = int(line.removeprefix("vlan "))
            if object_name in vlans:
                if vlans[object_name].get("managed"):
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


def generateVLANConfig(vlans: dict):
    config = []
    for id, fields in vlans.items():
        if fields.get("managed"):
            continue

        config.append("")  # Newline
        config.append(f"vlan {str(id)}")
        config.append(f"  name {fields['name']}")

    return config


def generateINTFConfig(interfaces: dict):
    """
    This is the main method that generates the cisco NXOS config from the interface manifest
    The output is ONLY the lines generated from the manifest, which needs to be combined with the existing running config

    :param interfaces: The interfaces manifest
    :type interfaces: dict
    :return: The generated NXOS config
    :rtype: list
    """

    def getLAGMembers(fields: dict):
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
    for intf, fields in interfaces.items():
        intf_num = intf.split(" ")[-1]

        # "fanout" field
        if "fanout" in fields:
            fanout_fields = fields["fanout"]
            nxos_mode_str = ""
            if fanout_fields["type"] == "quad":
                nxos_mode_str = "4x"
            elif fanout_fields["type"] == "dual":
                nxos_mode_str = "2x"
            elif fanout_fields["type"] == "single":
                nxos_mode_str = "1x"

            intf_port = intf_num.split("/")[-1]
            nxos_fanout_str = f"{fanout_fields['speed']}-{nxos_mode_str}"
            config_dict[
                f"interface breakout module 1 port {intf_port} map {nxos_fanout_str}"
            ] = []
            continue

        intf_cfg_label = intf
        dict_key = f"interface {intf_cfg_label}"
        if dict_key not in config_dict:
            config_dict[dict_key] = []

        is_portchannel = intf.startswith("port-channel")
        if is_portchannel:
            intf_num = intf[len("port-channel") :]

        # "description" field
        if "description" in fields:
            config_dict[dict_key].append(f"description {fields['description']}")

        # "enabled" field
        if "enabled" in fields:
            if fields["enabled"]:
                config_dict[dict_key].append("no shutdown")
            else:
                config_dict[dict_key].append("shutdown")

        # "mtu" field
        if "mtu" in fields:
            config_dict[dict_key].append(f"mtu {fields['mtu']}")

            if is_portchannel:
                for member_port in getLAGMembers(fields):
                    if member_port not in config_dict:
                        config_dict[member_port] = []

                    config_dict[member_port].append(f"mtu {fields['mtu']}")

        # "autoneg" field
        if "autoneg" in fields:
            if fields["autoneg"]:
                config_dict[dict_key].append("speed auto")
            else:
                config_dict[dict_key].append("no negotiate auto")

        # "speed" field
        if "speed" in fields:
            config_dict[dict_key].append(f"speed {fields['speed']}")

        # "fec" field
        if "fec" in fields:
            if fields["fec"]:
                config_dict[dict_key].append("fec auto")
            else:
                config_dict[dict_key].append("fec off")

        # Set to L3 mode if needed
        is_l3 = "ip4" in fields or "ip6" in fields
        if is_l3 and "Vlan" not in intf:
            config_dict[dict_key].append("no switchport")

        # "ip4" field
        if "ip4" in fields:
            config_dict[dict_key].append(f"ip address {fields['ip4']}")

        # "ip6" field
        if "ip6" in fields:
            config_dict[dict_key].append(f"ipv6 address {fields['ip6']}")

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
                untagged_str = f"switchport trunk native vlan {fields['untagged']}"
            elif fields["portmode"] == "access":
                untagged_str = f"switchport access vlan {fields['untagged']}"

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
                config_dict[member_port].append(f"vpc {fields['mlag']}")

    for key, lines in config_dict.items():
        config.append("")
        config.append(key)
        for line in lines:
            config.append(f"  {line}")

    return config


def NXOS_GETCONFIG(running_config: str, interfaces: dict, vlans: dict):
    """
    This is the main method that generates the config that will be applied on the switch
    It combines the VLAN and interface manifest with the existing running config

    :param running_config: The existing running config
    :type running_config: str
    :param interfaces: The interfaces manifest
    :type interfaces: dict
    :param vlans: The VLANs manifest
    :type vlans: dict
    :return: The generated NXOS config
    :rtype: str
    """
    parsedVLANs = getVLANList(running_config)
    outputVLANs = []

    outputVLANs.append("1")  # Default VLAN required
    for vlan, fields in vlans.items():
        # Carry forward default vlan, which is required
        if fields.get("managed"):
            if str(vlan) in parsedVLANs:
                outputVLANs.append(str(vlan))

            continue

        outputVLANs.append(str(vlan))

    new_config = removeOldLines(running_config, interfaces, vlans)

    vlan_cfg_str = "vlan " + ",".join(outputVLANs)
    new_config.append("")
    new_config.append(vlan_cfg_str)
    new_config += generateVLANConfig(vlans)

    new_config += generateINTFConfig(interfaces)

    out_config = "\n".join(new_config)
    return out_config


class FilterModule(object):
    def filters(self):
        return {"NXOS_GETCONFIG": NXOS_GETCONFIG}
