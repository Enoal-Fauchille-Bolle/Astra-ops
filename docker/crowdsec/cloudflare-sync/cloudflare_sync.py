"""Copy CrowdSec's own bans into a Cloudflare IP list, once a minute.

A WAF custom rule on the zone blocks every address in that list, so the bans also stop
visitors that come through Cloudflare, which the firewall bouncer never sees. Only local
decisions (origins `crowdsec` and `cscli`) are copied: the community list does not fit in
the 10,000 items of the free plan.

Each pass rewrites the whole list, so an expired ban leaves it on its own and there is no
state to keep. Cloudflare is only called when the set of addresses changed.
"""

import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

LAPI_URL = os.environ["CROWDSEC_LAPI_URL"].rstrip("/")
BOUNCER_KEY = os.environ["CROWDSEC_BOUNCER_KEY"]
CF_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
CF_ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
CF_LIST_NAME = os.environ.get("CLOUDFLARE_LIST_NAME", "crowdsec_bans")
KUMA_PUSH_URL = os.environ.get("KUMA_PUSH_URL", "")
INTERVAL = int(os.environ.get("SYNC_INTERVAL", "60"))

CF_LISTS = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/rules/lists"
CF_HEADERS = {"Authorization": f"Bearer {CF_TOKEN}"}
MAX_ITEMS = 10_000  # Free plan: one list, 10,000 items
FAILURES_BEFORE_DOWN = 5  # passes in a row, about five minutes
# Prefixes Cloudflare accepts in an IP list
MIN_PREFIX = {4: 8, 6: 12}


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def call(method, url, headers, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        # Cloudflare explains its refusals in the body
        raise RuntimeError(
            f"{method} {url}: {error.code} {error.read()[:300]!r}"
        ) from None
    return json.loads(payload) if payload else None


def local_bans():
    """Return {address: scenario} for the active local decisions."""
    query = urllib.parse.urlencode(
        {"startup": "true", "origins": "crowdsec,cscli", "scopes": "ip,range"}
    )
    stream = call(
        "GET", f"{LAPI_URL}/v1/decisions/stream?{query}", {"X-Api-Key": BOUNCER_KEY}
    )
    bans = {}
    for decision in (stream or {}).get("new") or []:
        if decision.get("simulated"):
            continue
        try:
            network = ipaddress.ip_network(decision["value"], strict=False)
        except ValueError:
            log(f"skipped {decision['value']!r}: not an address")
            continue
        if network.num_addresses == 1:
            address = str(network.network_address)
        elif network.prefixlen >= MIN_PREFIX[network.version]:
            address = str(network)
        else:
            log(f"skipped {network}: range too wide for a Cloudflare list")
            continue
        bans[address] = decision.get("scenario", "")[:100]
    return bans


def find_list_id():
    for item in call("GET", CF_LISTS, CF_HEADERS)["result"]:
        if item["name"] == CF_LIST_NAME:
            return item["id"]
    raise RuntimeError(f"no list named {CF_LIST_NAME!r} in account {CF_ACCOUNT}")


def replace_list(list_id, bans):
    """Replace every item of the list, then wait for Cloudflare to apply it."""
    items = [
        {"ip": address, "comment": scenario}
        for address, scenario in sorted(bans.items())
    ]
    result = call("PUT", f"{CF_LISTS}/{list_id}/items", CF_HEADERS, items)["result"]
    operation = result["operation_id"]
    for _ in range(30):
        time.sleep(2)
        status = call("GET", f"{CF_LISTS}/bulk_operations/{operation}", CF_HEADERS)[
            "result"
        ]
        if status["status"] == "completed":
            return
        if status["status"] == "failed":
            raise RuntimeError(f"Cloudflare refused the list: {status.get('error')}")
    raise RuntimeError(f"Cloudflare operation {operation} still pending after 60 s")


def push(status, message):
    if not KUMA_PUSH_URL:
        return
    query = urllib.parse.urlencode({"status": status, "msg": message})
    try:
        urllib.request.urlopen(f"{KUMA_PUSH_URL}?{query}", timeout=15).close()
    except OSError as error:
        log(f"Kuma push failed: {error}")


def main():
    list_id = None
    synced = None  # addresses Cloudflare holds since the last successful write
    failures = 0
    while True:
        try:
            bans = local_bans()
            if len(bans) > MAX_ITEMS:
                raise RuntimeError(
                    f"{len(bans)} bans, more than the {MAX_ITEMS} a list holds"
                )
            if set(bans) != synced:
                list_id = list_id or find_list_id()
                replace_list(list_id, bans)
                synced = set(bans)
                log(f"list updated: {len(bans)} addresses")
            failures = 0
            push("up", f"{len(bans)} addresses")
        except Exception as error:  # noqa: BLE001 - keep looping: the next pass may succeed
            failures += 1
            log(f"sync failed: {error}")
            # A passing Cloudflare or LAPI hiccup must not page Discord
            if failures >= FAILURES_BEFORE_DOWN:
                push("down", str(error)[:200])
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
