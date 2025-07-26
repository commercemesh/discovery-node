# Steps to Create PR from staging to main

## 1. Ensure your staging branch is up to date
```bash
git checkout staging
git pull origin staging
```

## 2. Check the changes that will be included
```bash
# See commits
git log main..staging --oneline

# See detailed changes
git diff main...staging --stat

# See full diff (optional)
git diff main...staging
```

## 3. Create PR via GitHub CLI (if installed)
```bash
gh pr create \
  --base main \
  --head staging \
  --title "Major Bug Fixes and New Features for Discovery Node" \
  --body-file PR_DESCRIPTION.md
```

## 4. Or create PR via GitHub Web Interface

1. Go to: https://github.com/commercemesh/discovery-node
2. Click "Pull requests" tab
3. Click "New pull request"
4. Set:
   - base: `main`
   - compare: `staging`
5. Click "Create pull request"
6. Copy the content from `PR_DESCRIPTION.md` into the description
7. Add reviewers if needed
8. Click "Create pull request"

## 5. Alternative: Push and create PR link
```bash
# Push your branch
git push origin staging

# GitHub will show a link in the output to create a PR
# Or visit: https://github.com/commercemesh/discovery-node/compare/main...staging
```

## PR Title
**Major Bug Fixes and New Features for Discovery Node**

## PR Labels (add these)
- `bug`
- `enhancement`
- `api`

## Summary of Changes

### Commits included:
1. `f4b5854` - BUG FIX: sending missing def _extract_media_from_jsonld
2. `6b4a297` - Fix MCP server to use same search service as API
3. `6f62229` - Fix MCP server database session management

### Files changed:
- 8 files modified
- 8 new files added (schemas, services, routes, tests)

### Key improvements:
1. Fixed @cmp:media extraction in search results
2. Fixed duplicate offers during ingestion
3. Added request ID generation and caching
4. Added product filtering with natural language
5. Added product comparison with recommendations

## Review Points
When creating the PR, highlight these for reviewers:
1. The duplicate offers fix is critical for data integrity
2. New APIs are backward compatible
3. All new features include comprehensive tests
4. Redis caching uses a separate database (db 2)