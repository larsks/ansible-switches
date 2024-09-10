import pytest

import cisco_nxos


@pytest.fixture
def running_config():
    return "\n".join(
        [
            "system default switchport",
            "",
            "vlan 1,10,105",
            "vlan 10",
            "  name CSAIL-MAIN",
            "vlan 105",
            "  name MOC-BU-PUBLIC",
            "",
            "vrf context management",
            "",
            "interface Ethernet1/1",
            "  description Test interface",
            "  switchport mode trunk",
            "  switchport access vlan 1",
            "  switchport trunk allowed vlan 10,105",
            "  speed 40000",
            "  no negotiate auto",
            "",
            "interface Ethernet1/2",
            "  shutdown",
            "",
            "no system default switchport shutdown",
        ]
    )


def test_removeOldLines_no_interface_no_vlan(running_config):
    expected_config = [
        "system default switchport",
        "",
        "vrf context management",
        "",
        "no system default switchport shutdown",
    ]
    res = cisco_nxos.removeOldLines(running_config, {}, {})
    assert res == expected_config


def test_removeOldLines_no_vlan(running_config):
    expected_config = [
        "system default switchport",
        "",
        "vrf context management",
        "",
        "interface Ethernet1/1",
        "  description Test interface",
        "  switchport mode trunk",
        "  switchport access vlan 1",
        "  switchport trunk allowed vlan 10,105",
        "  speed 40000",
        "  no negotiate auto",
        "",
        "no system default switchport shutdown",
    ]
    res = cisco_nxos.removeOldLines(
        running_config, {"Ethernet1/1": {"managed": True}}, {}
    )
    assert res == expected_config


def test_removeOldLines_no_interface(running_config):
    expected_config = [
        "system default switchport",
        "",
        "vlan 10",
        "  name CSAIL-MAIN",
        "vrf context management",
        "",
        "no system default switchport shutdown",
    ]
    res = cisco_nxos.removeOldLines(running_config, {}, {10: {"managed": True}})
    assert res == expected_config


# fmt: off
@pytest.mark.parametrize(
    "vlan_list_str, vlan_list_expected",
    [
        ("vlan 1",                  ["1"]),
        ("vlan 1,2,3",              ["1", "2", "3"]),
        ("vlan 1-3",                ["1", "2", "3"]),
        ("vlan 1,2-4,5",            ["1", "2", "3", "4", "5"]),
        ("vlan 1,2\nvlan 3,4\n",    ["1", "2"]),
    ],
)
# fmt: on
def test_getVLANList(vlan_list_str, vlan_list_expected):
    res = cisco_nxos.getVLANList(vlan_list_str)
    assert res == vlan_list_expected


def test_generateVLANConfig():
    vlans = {10: {"name": "example-vlan", "description": "Example vlan"}}
    res = cisco_nxos.generateVLANConfig(vlans)
    assert res == ["", "vlan 10", "  name example-vlan"]


@pytest.mark.parametrize(
    "iface_config, expected_config",
    [
        (
            {"Ethernet 1/1": {"enabled": True}},
            ["", "interface Ethernet 1/1", "  no shutdown"],
        ),
        (
            {"Ethernet 1/1": {"enabled": False}},
            ["", "interface Ethernet 1/1", "  shutdown"],
        ),
        (
            {"Ethernet 1/1": {"autoneg": True}},
            ["", "interface Ethernet 1/1", "  speed auto"],
        ),
        (
            {"Ethernet 1/1": {"autoneg": False}},
            ["", "interface Ethernet 1/1", "  no negotiate auto"],
        ),
        (
            {"Ethernet 1/1": {"fanout": {"type": "quad", "speed": "25G"}}},
            [
                "",
                "interface breakout module 1 port 1 map 25G-4x",
            ],
        ),
        (
            {"port-channel1": {"lag-members": ["Ethernet 1/1", "Ethernet 1/2"]}},
            [
                "",
                "interface port-channel1",
                "",
                "interface Ethernet 1/1",
                "  channel-group 1 mode on",
                "",
                "interface Ethernet 1/2",
                "  channel-group 1 mode on",
            ],
        ),
    ],
)
def test_generateINTFConfig(iface_config, expected_config):
    res = cisco_nxos.generateINTFConfig(iface_config)
    assert res == expected_config
