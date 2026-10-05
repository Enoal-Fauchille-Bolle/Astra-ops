"""Copy CrowdSec's own bans into a Cloudflare WAF custom rule, once a minute.

The rule blocks the addresses written in its own expression, so the bans also stop
visitors that come through Cloudflare, which the firewall bouncer never sees. Only local
decisions (origins `crowdsec` and `cscli`) are copied: the community list would never fit
in the 4,096 characters of an expression.

The addresses live in the rule, not in a Cloudflare IP list: since 2026-10-04 every write
to the account's lists answers 429 (code 10040), whatever the list and however long the
pause.

Each pass rewrites the whole expression, so an expired ban leaves it on its own and there
is no state to keep. Cloudflare is only called when the set of addresses changed.
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
CF_ZONE = os.environ["CLOUDFLARE_ZONE_ID"]
CF_RULE_NAME = os.environ.get("CLOUDFLARE_RULE_NAME", "CrowdSec bans")
# Kuma displays the URL with "?status=up&msg=OK&ping=" appended: keep only the part before "?"
KUMA_PUSH_URL = os.environ.get("KUMA_PUSH_URL", "").split("?")[0]
INTERVAL = int(os.environ.get("SYNC_INTERVAL", "60"))

CF_RULESETS = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE}/rulesets"
CF_ENTRYPOINT = f"{CF_RULESETS}/phases/http_request_firewall_custom/entrypoint"
USER_AGENT = {"User-Agent": "crowdsec-cloudflare-sync"}
CF_HEADERS = {"Authorization": f"Bearer {CF_TOKEN}", **USER_AGENT}
MAX_EXPRESSION = 4096  # characters, on every plan
# An empty set is not a valid expression: with no ban, the rule matches this address,
# reserved for documentation, so the script never has to disable the rule
NO_BAN = "192.0.2.1"
FAILURES_BEFORE_DOWN = 5  # passes in a row, about five minutes
MAX_BACKOFF = 1800  # seconds between two tries while Cloudflare answers 429
# Widest ranges copied, the limits of Cloudflare IP lists: a wider ban is surely a mistake
MIN_PREFIX = {4: 8, 6: 12}


class RateLimitedError(RuntimeError):
    """Cloudflare answered 429."""


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
        message = f"{method} {url}: {error.code} {error.read()[:300]!r}"
        if error.code == 429:
            raise RateLimitedError(message) from None
        raise RuntimeError(message) from None
    return json.loads(payload) if payload else None


def local_bans():
    """Return the addresses and ranges of the active local decisions."""
    query = urllib.parse.urlencode(
        {"startup": "true", "origins": "crowdsec,cscli", "scopes": "ip,range"}
    )
    stream = call(
        "GET", f"{LAPI_URL}/v1/decisions/stream?{query}", {"X-Api-Key": BOUNCER_KEY}
    )
    bans = set()
    for decision in (stream or {}).get("new") or []:
        if decision.get("simulated"):
            continue
        try:
            network = ipaddress.ip_network(decision["value"], strict=False)
        except ValueError:
            log(f"skipped {decision['value']!r}: not an address")
            continue
        if network.num_addresses == 1:
            bans.add(str(network.network_address))
        elif network.prefixlen >= MIN_PREFIX[network.version]:
            bans.add(str(network))
        else:
            log(f"skipped {network}: range too wide to copy")
    return bans


def expression(bans):
    return f"(ip.src in {{{' '.join(sorted(bans) or [NO_BAN])}}})"


def find_rule():
    """Return the zone's custom rules ruleset id and the rule named CF_RULE_NAME."""
    ruleset = call("GET", CF_ENTRYPOINT, CF_HEADERS)["result"]
    for rule in ruleset.get("rules") or []:
        if rule.get("description") == CF_RULE_NAME:
            return ruleset["id"], rule
    raise RuntimeError(f"no custom rule named {CF_RULE_NAME!r} in zone {CF_ZONE}")


def update_rule(new_expression):
    """Write the expression into the rule, keeping the rest as it is right now."""
    # Read just before writing: a rule disabled by hand must stay disabled
    ruleset_id, rule = find_rule()
    body = {
        key: rule[key]
        for key in ("action", "action_parameters", "description", "enabled")
        if key in rule
    }
    body["expression"] = new_expression
    call("PATCH", f"{CF_RULESETS}/{ruleset_id}/rules/{rule['id']}", CF_HEADERS, body)


def push(status, message):
    if not KUMA_PUSH_URL:
        return
    query = urllib.parse.urlencode({"status": status, "msg": message})
    # The push URL goes through Cloudflare, which refuses urllib's default User-Agent
    # (error 1010)
    request = urllib.request.Request(f"{KUMA_PUSH_URL}?{query}", headers=USER_AGENT)
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except OSError as error:
        log(f"Kuma push failed: {error}")


def main():
    synced = None  # the rule's expression, read at start then after each write
    failures = 0
    delay = INTERVAL
    while True:
        try:
            if synced is None:
                # A restart must not rewrite a rule that is already right
                synced = find_rule()[1]["expression"]
            bans = local_bans()
            wanted = expression(bans)
            if len(wanted) > MAX_EXPRESSION:
                raise RuntimeError(
                    f"{len(bans)} bans make {len(wanted)} characters, more than the "
                    f"{MAX_EXPRESSION} of an expression"
                )
            if wanted != synced:
                update_rule(wanted)
                synced = wanted
                log(f"rule updated: {len(bans)} addresses")
            failures = 0
            delay = INTERVAL
            push("up", f"{len(bans)} addresses")
        except Exception as error:  # noqa: BLE001 - keep looping: the next pass may succeed
            failures += 1
            # Read the rule again next pass: it may have been edited or recreated
            synced = None
            if isinstance(error, RateLimitedError):
                # Trying again every minute could keep Cloudflare's limit from lifting
                delay = min(delay * 2, MAX_BACKOFF)
            else:
                delay = INTERVAL
            log(f"sync failed, next try in {delay} s: {error}")
            # A passing Cloudflare or LAPI hiccup must not page Discord
            if failures >= FAILURES_BEFORE_DOWN:
                push("down", str(error)[:200])
        time.sleep(delay)


if __name__ == "__main__":
    main()
