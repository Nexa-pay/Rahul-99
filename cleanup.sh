#!/bin/bash
# Cleanup old logs and temp files
find /tmp -type f -atime +1 -delete
find /var/log -name "*.log" -size +10M -delete
