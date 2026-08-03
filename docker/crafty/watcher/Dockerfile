# Patched build of the upstream Crafty Server Watcher.
#
# Upstream has a race condition that lets the proxy re-bind the Minecraft port
# while a server start is in flight, so the real MC server dies with
# "FAILED TO BIND TO PORT". See README.md for the full analysis.
#
# Once the fix lands upstream: delete this Dockerfile and put the plain
# `image:` reference back in ../docker-compose.yml.
FROM ghcr.io/soveticka/crafty-server-watcher:latest@sha256:d5bd23f29e75dc514498e0387b39bab17fd3141e8fa1ab93e8412a851730e485

COPY patch_start_race.py /tmp/patch_start_race.py
RUN python3 /tmp/patch_start_race.py && rm /tmp/patch_start_race.py
