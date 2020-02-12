# Copyright 2020 Datawire. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

########
# This is a debugging tool that, given an envoy.json _generated by Ambassador_, will
# dump a simplified view of the routing table implemented by that envoy.json.
#
# **NOTE WELL** that this is not a general-purpose Envoy visualization tool. It is
# very specific to Ambassador.
########

from typing import Any, Optional

import functools
import json
import re

from collections import OrderedDict

import click
import dpath

def lookup(x: Any, path: str) -> Optional[Any]:
    try:
        return dpath.util.get(x, path)
    except KeyError:
        return None


reSecret = re.compile(r'^.*/snapshots/([^/]+)/secrets-decoded/([^/]+)/[0-9A-F]+\.(.+)$')

# Use this instead of click.option
click_option = functools.partial(click.option, show_default=True)
click_option_no_default = functools.partial(click.option, show_default=False)

@click.command(help="Show a simplified Envoy config breakdown")
@click.argument('envoy-config-path', type=click.Path(exists=True, readable=True))
def main(envoy_config_path: str) -> None:
    econf = json.load(open(envoy_config_path, "r"))

    listeners = lookup(econf, "/static_resources/listeners") or []

    for listener in listeners:
        bind_addr = lookup(listener, "/address/socket_address/address")
        port = lookup(listener, "/address/socket_address/port_value")
        proto = lookup(listener, "/address/socket_address/protocol")

        lfilters = lookup(listener, "/listener_filters")
        lfiltstr = ""

        if lfilters:
            lfilter_names = [ x["name"].replace("envoy.listener.", "") for x in lfilters ]
            lfiltstr = f" [using {', '.join(lfilter_names)}]"

        print(f"LISTENER on {proto} {bind_addr}:{port}{lfiltstr}")

        for chain in listener["filter_chains"]:
            upp = chain.get("use_proxy_proto", False)
            match_proto = lookup(chain, "/filter_chain_match/transport_protocol")
            match_domains = lookup(chain, "/filter_chain_match/server_names")

            match_domain_str = '*'

            if match_domains:
                match_domain_str = "/".join(match_domains)

            chain_options = []

            if match_proto == "tls":
                chain_options.append("TLS-only")

            ctx = lookup(chain, "/tls_context/common_tls_context/tls_certificates/0") or None
            ctx_name = None

            if ctx:
                for el in ctx.values():
                    fname = el.get("filename")

                    if fname:
                        m = reSecret.match(fname)

                        if m:
                            secret_name = m.group(2)
                            secret_namespace = m.group(1)

                            ctx_name = f"{secret_name}.{secret_namespace}"
                            break

            if ctx_name:
                chain_options.append(f"ctx {ctx_name}")

            if upp:
                chain_options.append("with PROXY proto")

            chain_option_str = ""

            if chain_options:
                chain_option_str = f" ({', '.join(chain_options)})"

            print(f"... CHAIN {match_domain_str}{chain_option_str}")

            filters = chain["filters"]

            for filter in filters:
                if filter["name"] == "envoy.http_connection_manager":
                    vhosts = lookup(filter, "/config/route_config/virtual_hosts")

                    for vhost in vhosts:
                        domains = vhost["domains"]
                        routes = vhost["routes"]

                        print(f"... ... VHOST {', '.join(domains)}")

                        actions = OrderedDict()

                        for route in routes:
                            match = route["match"]
                            pfx = match.get("prefix") or "-no-prefix-"
                            headers = match.get("headers") or []
                            security = "insecure"
                            authority = ""
                            header_count = 0
                            action = "Unknown"

                            if headers:
                                for hdr in headers:
                                    if (hdr["name"] == "x-forwarded-proto") and (hdr.get("exact_match") == "https"):
                                        security = "secure"
                                    elif hdr["name"] == ":authority":
                                        authority = f"@{hdr['exact_match']}"
                                    else:
                                        header_count += 1

                            hdr_str = ""

                            if header_count > 0:
                                hdr_str = f" ({header_count} additional header{'' if header_count == 1 else 's'})"

                            target = f"{pfx}{authority}{hdr_str}"

                            action_list = actions.setdefault(target, [])

                            if route.get("route"):
                                action = "Route"
                            elif route.get("redirect"):
                                action = "Redirect"

                            action_list.append(f"{action} {security}")

                        for target, action_list in actions.items():
                            print(f"... ... ... {target}: {'; '.join(action_list)}")


if __name__ == '__main__':
    main()