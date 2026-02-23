#!/bin/bash

filename=$1
tempfilename="temp_${filename}"

# Replace a single double-quote with two double-quotes to escape them
sed 's/"/""/g' "${filename}" > "${tempfilename}"

# Revert the surrounding character from a pipe | to a double-quote "
sed 's/|/"/g' "${tempfilename}" > "${filename}"

# Replace "NULL" with "#N/A"
sed 's/"NULL"/"#N\/A"/g' "${filename}" > "${tempfilename}"

# Replace ,NULL, with ,#N/A,
sed 's/,NULL,/,#N\/A,/g' "${tempfilename}" > "${filename}"

# Replace ,NULL with ,#N/A
sed 's/,NULL\n/,#N\/A\n/g' "${filename}" > "${tempfilename}"

# Move the temp file back over to the real filename
mv "${tempfilename}" "${filename}"


