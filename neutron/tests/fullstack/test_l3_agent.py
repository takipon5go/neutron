# Copyright 2015 Red Hat, Inc.
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

from neutron.agent.l3 import agent as l3_agent
from neutron.agent.l3 import namespaces
from neutron.agent.linux import ip_lib
from neutron.agent.linux import utils
from neutron.openstack.common import uuidutils
from neutron.tests.fullstack import base
from neutron.tests.fullstack import fullstack_fixtures as f_fixtures


class SingleNodeEnvironment(f_fixtures.FullstackFixture):
    def setUp(self):
        super(SingleNodeEnvironment, self).setUp()

        neutron_config = self.neutron_server.neutron_cfg_fixture
        ml2_config = self.neutron_server.plugin_cfg_fixture

        self.ovs_agent = self.useFixture(
            f_fixtures.OVSAgentFixture(
                neutron_config, ml2_config))

        self.l3_agent = self.useFixture(
            f_fixtures.L3AgentFixture(
                self.temp_dir,
                neutron_config,
                self.ovs_agent._get_br_int_name()))

        self.wait_until_env_is_up(agents_count=2)


class TestLegacyL3Agent(base.BaseFullStackTestCase):
    def __init__(self, *args, **kwargs):
        super(TestLegacyL3Agent, self).__init__(
            SingleNodeEnvironment(), *args, **kwargs)

    def _get_namespace(self, router_id):
        return namespaces.build_ns_name(l3_agent.NS_PREFIX, router_id)

    def _assert_namespace_exists(self, ns_name):
        ip = ip_lib.IPWrapper(ns_name)
        utils.wait_until_true(lambda: ip.netns.exists(ns_name))

    def test_namespace_exists(self):
        uuid = uuidutils.generate_uuid()

        router = self.client.create_router(
            body={'router': {'name': 'router-test',
                             'tenant_id': uuid}})

        network = self.client.create_network(
            body={'network': {'name': 'network-test',
                              'tenant_id': uuid}})

        subnet = self.client.create_subnet(
            body={'subnet': {'name': 'subnet-test',
                             'tenant_id': uuid,
                             'network_id': network['network']['id'],
                             'cidr': '20.0.0.0/24',
                             'gateway_ip': '20.0.0.1',
                             'ip_version': 4,
                             'enable_dhcp': True}})

        self.client.add_interface_router(
            router=router['router']['id'],
            body={'subnet_id': subnet['subnet']['id']})

        router_id = router['router']['id']
        namespace = "%s@%s" % (
            self._get_namespace(router_id),
            self.environment.l3_agent.get_namespace_suffix(), )
        self._assert_namespace_exists(namespace)

        self.client.remove_interface_router(
            router=router['router']['id'],
            body={'subnet_id': subnet['subnet']['id']})

        self.client.delete_subnet(subnet['subnet']['id'])
        self.client.delete_network(network['network']['id'])
        self.client.delete_router(router['router']['id'])
