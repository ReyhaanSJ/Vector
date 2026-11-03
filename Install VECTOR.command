#!/bin/bash
# Double-click me on a Mac to install or update VECTOR.
# (If macOS says it can't be opened: right-click this file > Open > Open.)
cd "$(dirname "$0")" || exit 1
/bin/bash ./install.sh
echo
read -r -n 1 -p "Press any key to close this window." _
echo
