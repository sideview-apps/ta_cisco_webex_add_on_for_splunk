#!/bin/bash
# Build this add-on and relink a dev box's local config into the build.
#
# On Sideview's dev box, $SPLUNK_HOME/etc/apps/ta_cisco_webex_add_on_for_splunk
# is a symlink to output/ta_cisco_webex_add_on_for_splunk here.  ucc-gen build
# --overwrite deletes that directory, so local/ (the account, its OAuth tokens
# in passwords.conf, and the input stanzas) and metadata/local.meta cannot live
# in it.  They live in LOCAL_STATE instead and are linked back in after every
# build.  The rebuild removes the links, never what they point at.
#
# Build only through this script.  A bare "ucc-gen build" leaves the app with
# no local config: no account and no enabled inputs until this is rerun.
#
# v1.4.2 and later need ucc-gen==6.4.0; see the fork's notes.

set -euo pipefail
cd "$(dirname "$0")"

# WEBEX_TA_LOCAL_STATE is the directory holding local/ and local.meta, set in
# the dev box's shell profile.
LOCAL_STATE=${WEBEX_TA_LOCAL_STATE:?set WEBEX_TA_LOCAL_STATE to the directory holding local/ and local.meta}
OUT=output/ta_cisco_webex_add_on_for_splunk

if [ ! -d "$LOCAL_STATE/local" ] || [ ! -f "$LOCAL_STATE/local.meta" ]; then
    echo "expected $LOCAL_STATE/local/ and $LOCAL_STATE/local.meta" >&2
    exit 1
fi

# Without --ta-version, ucc-gen stamps "<version>+<git hash>" into the SOURCE
# globalConfig.json, which then shows up as a change to commit.
VERSION=$(python3 -c "import json; print(json.load(open('globalConfig.json'))['meta']['version'])")
ucc-gen build --overwrite --ta-version "$VERSION" "$@"
ln -s "$LOCAL_STATE/local" "$OUT/local"
ln -s "$LOCAL_STATE/local.meta" "$OUT/metadata/local.meta"
echo "built $(cat "$OUT/VERSION") and linked local config from $LOCAL_STATE"
