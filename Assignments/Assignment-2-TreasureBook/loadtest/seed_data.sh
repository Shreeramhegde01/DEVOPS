#!/usr/bin/env bash
# Creates the example graph from the assignment's analogy table, then queries it.
# Usage: ./seed_data.sh http://127.0.0.1:30080      (default http://localhost:5000)
set -euo pipefail
BASE="${1:-http://localhost:5000}"

post() { curl -sf -X POST "$BASE/$1" -H "Content-Type: application/json" -d "$2"; echo; }

echo "== Nodes (Treasure / Location / Map)"
post node '{"type":"Treasures","name":"Golden Crown","properties":{"era":"Medieval","value":"priceless"}}'
post node '{"type":"Treasure","name":"Cursed Diamond","properties":{"carats":45}}'
post node '{"type":"Location","name":"Cave of Wonders"}'
post node '{"type":"Location","name":"Forest of Secrets"}'
post node '{"type":"Location","name":"Mystic Lake"}'
post node '{"type":"Map","name":"Mystic Map","properties":{"condition":"torn"}}'

echo "== Edges (Trail / Hidden-At / Leads-To) - nodes can be referenced by name or id"
post edge '{"type":"Hidden-At","from":"Golden Crown","to":"Cave of Wonders"}'
post edge '{"type":"Trail","from":"Forest of Secrets","to":"Mystic Lake","properties":{"difficulty":"hard"}}'
post edge '{"type":"Trail","from":"Mystic Lake","to":"Cave of Wonders"}'
post edge '{"type":"Leads-to","from":"Mystic Map","to":"Cursed Diamond"}'

echo "== Neighbours of Cave of Wonders"
curl -sf "$BASE/node/Cave%20of%20Wonders/neighbors"; echo
echo "== Shortest trail from Forest of Secrets to Golden Crown"
curl -sf "$BASE/path?from=Forest%20of%20Secrets&to=Golden%20Crown"; echo
echo "== Stats"
curl -sf "$BASE/stats"; echo
