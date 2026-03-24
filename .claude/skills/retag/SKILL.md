---
name: retag
description: "Move the most recent git tag to the current commit and push it. Use when the user says /retag, 'move the tag', 'update the tag', 'retag', or wants to point the latest tag at HEAD."
---

Move the most recent git tag to the current HEAD commit and update the remote. Do NOT ask for confirmation — just do it.

## Steps

Run all of this without pausing for user input:

1. Get the most recent tag. If no tags exist, tell the user "No tags found in this repo" and stop.

2. Check if the tag is already on HEAD. If so, tell the user and stop.

3. Delete the local tag, recreate it on HEAD preserving the original message, and push to remote:

```bash
TAG=$(git describe --tags --abbrev=0)
TAG_COMMIT=$(git rev-list -n 1 "$TAG")
HEAD_COMMIT=$(git rev-parse HEAD)
if [ "$TAG_COMMIT" = "$HEAD_COMMIT" ]; then
  echo "ALREADY_ON_HEAD"
  exit 0
fi
MSG=$(git tag -l --format='%(contents)' "$TAG")
git tag -d "$TAG"
git tag -a "$TAG" -m "${MSG:-$TAG}"
git push origin ":refs/tags/$TAG"
git push origin "$TAG"
echo "MOVED $TAG to $(git rev-parse --short HEAD)"
```

4. Confirm to the user: "Moved `{tag}` to `{short HEAD hash}` and pushed to remote."
