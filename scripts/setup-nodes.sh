#!/bin/bash
# Create 3 agent nodes on the center server
set -e

CENTER="http://localhost:9191"

# Login to get JWT cookie
echo "=== Logging in ==="
curl -s -c /tmp/cookies.txt -X POST "$CENTER/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}' | python3 -m json.tool

# Create nodes
for i in 1 2 3; do
  NAME="agent-node-$i"
  echo ""
  echo "=== Creating node: $NAME ==="
  curl -s -b /tmp/cookies.txt -X POST "$CENTER/api/nodes" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$NAME\"}" | python3 -m json.tool
done

echo ""
echo "=== All nodes created ==="
