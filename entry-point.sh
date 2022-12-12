#!/bin/sh

until cd /app/opal_fetcher_ceph
do
    echo "Waiting for server volume..."
done
echo "Server Volume Mounted"
