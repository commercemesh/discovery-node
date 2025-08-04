#!/bin/bash

echo "=== Local Multi-Tenant Testing Guide ==="
echo

echo "1. First, add these entries to your /etc/hosts file:"
echo "   sudo nano /etc/hosts"
echo
echo "   Add these lines:"
echo "   127.0.0.1    insighteditions.localhost"
echo "   127.0.0.1    acme-solutions.localhost"
echo
echo "2. Set environment variables:"
echo "   export MULTI_TENANT_MODE=true"
echo "   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cmp_discovery"
echo
echo "3. Run the database migration:"
echo "   cd /Users/shiv/Documents/CMP/discovery/discovery-node"
echo "   alembic upgrade head"
echo
echo "4. Start the server:"
echo "   python main.py serve"
echo
echo "5. In another terminal, run test queries:"
echo

# Test commands
echo "=== Test Commands ==="
echo

echo "# Test health check (no subdomain needed)"
echo "curl http://localhost:8000/health"
echo

echo "# Test without subdomain (should fail in multi-tenant mode)"
echo "curl http://localhost:8000/api/v1/search?q=test"
echo

echo "# Test with Insight Editions subdomain"
echo "curl http://insighteditions.localhost:8000/api/v1/search?q=star+wars"
echo

echo "# Test with Acme Solutions subdomain"
echo "curl http://acme-solutions.localhost:8000/api/v1/search?q=products"
echo

echo "# Test product by URN with subdomain"
echo 'curl http://insighteditions.localhost:8000/api/v1/products/urn:cmp:product:star-wars-book'
echo

echo "=== Alternative: Using Host Header ==="
echo

echo "# If you can't modify /etc/hosts, use the Host header:"
echo 'curl -H "Host: insighteditions.localhost:8000" http://localhost:8000/api/v1/search?q=test'
echo 'curl -H "Host: acme-solutions.localhost:8000" http://localhost:8000/api/v1/search?q=test'