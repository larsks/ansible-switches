# Ansible Site for Managing MOC/OCT Switches
Ansible site for MOC/OCT switches

## Supported Switch OSes

* Dell OS9 (FTOS9)
* Cisco NXOS

## Site Setup

1. Install newest version of ansible
1. Install required PyPI packages:
    1. `pip install --user ansible-pylibssh`
1. Install the required ansible modules: `ansible-galaxy collection install -r requirements.yaml`
1. Set up AWS CLI and be sure you can access the correct secrets
1. On your client, you may have to enable legacy kex algorithms for some switches:
    ```
    KexAlgorithms +diffie-hellman-group1-sha1,diffie-hellman-group14-sha1
    ```

## Configuration

### Interfaces

Interfaces are configured in the file `host_vars/HOST/interfaces.yaml`

An example of this file is below:

```
interfaces:
  twentyFiveGigE 1/1:
    description: "example interface"
    state: "up"
    mtu: 9216
  Port-channel 1:
    state: "up"
    lag-members:
      - "hundredGigE 1/1"
      - "hundredGigE 1/2"
    portmode: "access"
    untagged: 10
  Vlan 207:
    state: "up"
    ip4: "10.10.10.10/20"
```

### Available Fields

* `name` Only for VLANs, sets the name of interfaces. (String)
* `description` Sets the description of the interface. (String)
* `state` Sets the admin state of the mode ("up", or "down")
* `mtu` Sets the MTU of the interface (Integer 576-9416)
* `fec` If false, forward-error-correction is disabled on the interface (Boolean)
* `autoneg` If false, auto-negotiation is disabled on the interface (Boolean)
* `stp` Sets STP Parameters
  * `edgeport` Sets whether port should be an edge port (Boolean)
  * `bpduguard` Enables BPDUguard on an interface (Boolean)
  * `rootguard` Enables Rootguard on an interface (Boolean)
  * `disabled` Disables STP on the interface (Boolean)
* `fanout` Sets fanout configuration
  * `mode` Sets mode (`single`, `dual`, or `quad`)
  * `speed` Sets the fanout speed (`10G`, `25G`, or `40G`)
* `managed` If true, this interface will not be configured by ansible. Works for both VLANs and interfaces (Boolean)
* `portmode` L2 portmode of an interface (String "access", "trunk", or "hybrid")
* `untagged` Single vlan to untag, requires portmode access or hybrid (Integer 2-4094)
* `tagged` List of vlans to tag, requires portmode trunk or hybrid (List of Integers 2-4094)
* `ip4` Sets the IPv4 address of the interface (String "X.X.X.X/YY")
* `ip6` Sets the IPv6 address of the interface (String)
* `lag-members` List of non-LACP lag members for a port channel (List of Strings, interface names)
* `lacp-members-active` List of LACP active members for a port channel (List of Strings, interface names)
* `lacp-members-passive` List of LACP passive members for a port channel (List of Strings, interface names)
* `lacp-rate` Sets the switch rate for LACP only (String "fast" or "slow")
* `mlag` Set the label of the peer port-channel for a paired switch (String interface name)

## Switch Configuration

Switches will need some manual configuration before being able to be set up from this ansible site.

### Dell OS9 Switches

1. On the switch, enter `conf` mode
1. Set the enable password: `enable password <DEFAULT_OS9_PASSWD>`
1. Set the ssh user `username admin password <DEFAULT_OS9_PASSWD>`
1. Enable ssh server `ip ssh server enable`
1. Set the access IP (usually `managementethernet 1/1`)

## License

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this project except in compliance with the License. You may obtain
a copy of the License at <http://www.apache.org/licenses/LICENSE-2.0>.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.

