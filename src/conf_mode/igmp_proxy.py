#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
import os
import jinja2

from vyos.config import Config
from vyos import ConfigError

config_file = r'/etc/igmpproxy.conf'

# Please be careful if you edit the template.
config_tmpl = """
########################################################
#
# autogenerated by igmp_proxy.py
#
#   The configuration file must define one upstream
#   interface, and one or more downstream interfaces.
#
#   If multicast traffic originates outside the
#   upstream subnet, the "altnet" option can be
#   used in order to define legal multicast sources.
#   (Se example...)
#
#   The "quickleave" should be used to avoid saturation
#   of the upstream link. The option should only
#   be used if it's absolutely nessecary to
#   accurately imitate just one Client.
#
########################################################

{% if not disable_quickleave -%}
quickleave
{% endif -%}

{% for i in interface %}
# Configuration for {{ i.interface }} ({{ i.role }} interface)
{% if i.role == 'disabled' -%}
phyint {{ i.interface }} disabled
{%- else -%}
phyint {{ i.interface }} {{ i.role }} ratelimit 0 threshold {{ i.threshold }}
{%- endif -%}
{%- for subnet in i.alt_subnet %}
        altnet {{ subnet }}
{%- endfor %}
{%- for subnet in i.whitelist %}
        whitelist {{ subnet }}
{%- endfor %}
{% endfor %}
"""

default_config_data = {
    'disable': False,
    'disable_quickleave': False,
    'interface': [],
}

def get_config():
    igmp_proxy = default_config_data
    conf = Config()
    if not conf.exists('protocols igmp-proxy'):
        return None
    else:
        conf.set_level('protocols igmp-proxy')

    # Network interfaces to listen on
    if conf.exists('disable'):
        igmp_proxy['disable'] = True

    # Option to disable "quickleave"
    if conf.exists('disable-quickleave'):
        igmp_proxy['disable_quickleave'] = True

    for intf in conf.list_nodes('interface'):
        conf.set_level('protocols igmp-proxy interface {0}'.format(intf))
        interface = {
            'interface': intf,
            'alt_subnet': [],
            'role': 'downstream',
            'threshold': '1',
            'whitelist': []
        }

        if conf.exists('alt-subnet'):
            interface['alt_subnet'] = conf.return_values('alt-subnet')

        if conf.exists('role'):
            interface['role'] = conf.return_value('role')

        if conf.exists('threshold'):
            interface['threshold'] = conf.return_value('threshold')

        if conf.exists('whitelist'):
            interface['whitelist'] = conf.return_values('whitelist')

        # Append interface configuration to global configuration list
        igmp_proxy['interface'].append(interface)

    return igmp_proxy

def verify(igmp_proxy):
    # bail out early - looks like removal from running config
    if igmp_proxy is None:
        return None

    # bail out early - service is disabled
    if igmp_proxy['disable']:
        return None

    # at least two interfaces are required, one upstream and one downstream
    if len(igmp_proxy['interface']) < 2:
        raise ConfigError('Must define an upstream and at least 1 downstream interface!')

    upstream = 0
    for i in igmp_proxy['interface']:
        if "upstream" == i['role']:
            upstream += 1

    if upstream == 0:
        raise ConfigError('At least 1 upstream interface is required!')
    elif upstream > 1:
        raise ConfigError('Only 1 upstream interface allowed!')

    return None

def generate(igmp_proxy):
    # bail out early - looks like removal from running config
    if igmp_proxy is None:
        return None

    # bail out early - service is disabled, but inform user
    if igmp_proxy['disable']:
        print('Warning: IGMP Proxy will be deactivated because it is disabled')
        return None

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(igmp_proxy)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(igmp_proxy):
    if igmp_proxy is None or igmp_proxy['disable']:
         # IGMP Proxy support is removed in the commit
         os.system('sudo systemctl stop igmpproxy.service')
         if os.path.exists(config_file):
             os.unlink(config_file)
    else:
        os.system('sudo systemctl restart igmpproxy.service')

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)