#!/usr/bin/env bash
# setup-offline.sh
#
# Prepares required Docker images for running catalyst-ci-test
# in an air-gapped / isolated network.
#
# Run this script on a machine WITH internet access, then transfer
# the generated .tar files to your isolated environment and load them.
#
# Usage:
#   # On machine with internet:
#   ./scripts/setup-offline.sh save
#
#   # Transfer the .tar files, then on isolated machine:
#   ./scripts/setup-offline.sh load

set -euo pipefail

IMAGES=(
    "firecow/gitlab-ci-local-util:latest"
)

OUTDIR="$(dirname "$0")/../.offline-images"

case "${1:-help}" in
    save)
        mkdir -p "$OUTDIR"
        for img in "${IMAGES[@]}"; do
            filename="$(echo "$img" | tr '/:' '_').tar"
            echo "Pulling $img ..."
            docker pull "$img"
            echo "Saving to $OUTDIR/$filename ..."
            docker save "$img" -o "$OUTDIR/$filename"
        done
        echo ""
        echo "Done! Transfer the files in $OUTDIR/ to your isolated machine,"
        echo "then run:  ./scripts/setup-offline.sh load"
        ;;
    load)
        if [ ! -d "$OUTDIR" ]; then
            echo "Error: $OUTDIR not found. Run 'save' first on a machine with internet."
            exit 1
        fi
        for tarfile in "$OUTDIR"/*.tar; do
            echo "Loading $(basename "$tarfile") ..."
            docker load -i "$tarfile"
        done
        echo ""
        echo "Done! All images loaded. You can now run catalyst-ci-test."
        ;;
    *)
        echo "Usage: $0 {save|load}"
        echo ""
        echo "  save   Pull and save required Docker images to .tar files"
        echo "  load   Load .tar files into the local Docker daemon"
        exit 1
        ;;
esac
