# Copyright (C) 2011 Midokura KK
# Copyright (C) 2011 Nicira, Inc
# Copyright 2011 OpenStack Foundation
# Copyright 2018 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from os_vif import objects
from os_vif import plugin

from oslo_config import cfg
from oslo_log import log as logging
from nova.privsep import linux_net

LOG = logging.getLogger(__name__)

class NoOpPlugin(plugin.PluginBase):
    """A no op plugin

    The no op plugin can be used for any vif type that requires
    no action to be performed on the backend network when a vif
    is plugged. Currently only the VIFVHostUser VIF type is supported.
    This pluggin allows for the use of generic vhost user without ovs.

    """

    @classmethod
    def load(cls, plugin_name, config=None):
        return cls(config)
    
    def __init__(self, config=None):
        self.config = config or {}

    def describe(self):
        return objects.host_info.HostPluginInfo(
            plugin_name="cilium",
            vif_info=[],
        )

    def plug(self, vif, instance_info):
        devname = getattr(vif, "dev_name", None)
        mac = getattr(vif, "address", None)

        if not devname or not mac:
            raise Exception(f"Cilium plugin: Missing dev_name or address (dev_name={devname}, mac={mac})")

        LOG.info("Cilium plugin: Creating TAP device %s with MAC %s", devname, mac)
        linux_net.create_tap_dev(devname, mac, multiqueue=False)

        # Set default MTU if not provided
        mtu = getattr(vif.network, "mtu", 1500)  # Default to 1500
        try:
            linux_net.set_device_mtu(devname, mtu)
        except Exception as e:
            LOG.warning("Failed to set MTU on %s: %s", devname, str(e))

        ip_address = vif.details.get('ip_address')
        prefixlen = vif.details.get('prefixlen')
        if ip_address and prefixlen:
            LOG.info("Assigning IP %s to device %s", ip_address, devname)
            try:
                linux_net.add_ip_to_dev(devname, ip_address, prefixlen)  # Adjust prefix length
            except Exception as e:
                LOG.warning("Failed to assign IP %s to %s: %s", ip_address, devname, str(e))

        try:
            linux_net.set_device_enabled(devname)
        except Exception as e:
            LOG.warning("Failed to enable device %s: %s", devname, str(e))

    def unplug(self, vif, instance_info):
        devname = getattr(vif, "dev_name", None)
        if devname:
            LOG.info("Cilium plugin: Deleting TAP device %s", devname)
            try:
                linux_net.delete_net_dev(devname)
            except Exception as e:
                LOG.warning("Failed to delete TAP device %s: %s", devname, str(e))
        else:
            LOG.warning("Cilium plugin: No dev_name to unplug")
