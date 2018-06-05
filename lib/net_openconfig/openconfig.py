# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Copyright (c) 2017 Red Hat Inc.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import json
import q
from difflib import Differ
from copy import deepcopy
from time import sleep

from ansible.module_utils._text import to_text, to_bytes
from ansible.module_utils.basic import env_fallback
from ansible.module_utils.network.common.utils import to_list
from ansible.module_utils.network.common.netconf import NetconfConnection

try:
    from ncclient.xml_ import to_xml
    HAS_NCCLIENT = True
except ImportError:
    HAS_NCCLIENT = False

try:
    from lxml import etree
    HAS_XML = True
except ImportError:
    HAS_XML = False

try:
    from lxml.etree import tostring
except ImportError:
    from xml.etree.ElementTree import tostring

_EDIT_OPS = frozenset(['merge', 'create', 'replace', 'delete'])

BASE_1_0 = "{urn:ietf:params:xml:ns:netconf:base:1.0}"

def get_connection(module):
    if hasattr(module, 'connection'):
        return module.connection

    module.connection = NetconfConnection(module._socket_path)

    return module.connection


def get_device_capabilities(module):
    if hasattr(module, 'capabilities'):
        return module.capabilities

    capabilities = NetconfConnection(module._socket_path).get_capabilities()
    module.capabilities = json.loads(capabilities)

    return module.capabilities


def is_netconf(module):
    capabilities = get_device_capabilities(module)
    network_api = capabilities.get('network_api')
    if network_api not in ('cliconf', 'netconf'):
        module.fail_json(msg=('unsupported network_api: {!s}'.format(network_api)))
        return False

    if network_api == 'netconf':
        if not HAS_NCCLIENT:
            module.fail_json(msg=('ncclient is not installed'))
        if not HAS_XML:
            module.fail_json(msg=('lxml is not installed'))

        return True

    return False


def get_config_diff(module, running=None, candidate=None):
    conn = get_connection(module)

    if is_netconf(module):
        if running and candidate:
            running_data = running.split("\n", 1)[1].rsplit("\n", 1)[0]
            candidate_data = candidate.split("\n", 1)[1].rsplit("\n", 1)[0]
            if running_data != candidate_data:
                d = Differ()
                diff = list(d.compare(running_data.splitlines(), candidate_data.splitlines()))
                return '\n'.join(diff).strip()

    return None


def discard_config(module):
    conn = get_connection(module)
    conn.discard_changes()


def commit_config(module, comment=None, confirmed=False, confirm_timeout=None, persist=False, check=False):
    conn = get_connection(module)
    reply = None

    if check:
        reply = conn.validate()
    else:
        if is_netconf(module):
            reply = conn.commit(confirmed=confirmed, timeout=confirm_timeout, persist=persist)
    return reply


def get_oper(module, filter=None):
    conn = get_connection(module)

    if filter is not None:
        response = conn.get(filter)
    else:
        return None

    return to_bytes(etree.tostring(response), errors='surrogate_then_replace').strip()


def get_config(module, config_filter=None, source='running'):
    conn = get_connection(module)

    # Note: Does not cache config in favour of latest config on every get operation.
    out = conn.get_config(source=source, filter=config_filter)
    if is_netconf(module):
        out = to_xml(conn.get_config(source=source, filter=config_filter))

    cfg = out.strip()

    return cfg


def load_config(module, command_filter, commit=False, replace=False,
                comment=None, admin=False, running=None, nc_get_filter=None):

    conn = get_connection(module)

    diff = None
    if is_netconf(module):
        # FIXME: check for platform behaviour and restore this
        # conn.lock(target = 'candidate')
        # conn.discard_changes()

        try:
            for filter in to_list(command_filter):
                conn.edit_config(filter)

            candidate = get_config(module, source='candidate', config_filter=nc_get_filter)
            diff = get_config_diff(module, running, candidate)

            if commit and diff:
                commit_config(module)
            else:
                discard_config(module)
        finally:
            # conn.unlock(target = 'candidate')
            pass

    return diff

class Config(object):

    def __init__(self, module):
        self.__module = module
        self._schema_cache = None
        self._config = None

    def get_all_schemas(self):
        conn = get_connection(self._module)
        content = '''
          <filter>                                                                                                        
            <netconf-state xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">                                   
              <schemas>
                <schema>
                    <identifier/>
                </schema>
              </schemas>                                                                                                  
            </netconf-state>                                                                                              
          </filter>          
        '''
        xml_request = '<%s>%s</%s>' %('get', content, 'get')
        response = conn.dispatch(xml_request)
        res = tostring(response)
        q(res)
        self._schema_cache = res
        return res

    def find_schema_xmlns(self, schema_key):
        if self._schema_cache == None:
            self._schema_cache = self.get_all_schemas()
        # Search for schema in schema supported by device


           


    

