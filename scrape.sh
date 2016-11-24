#!/usr/bin/env bash

query="trump"
doc_type="Blog"
date_range="9/25/2016 11/23/2016"

python wapo.py -q $query -t $doc_type
python nyt.py -q $query -t $doc_type -r $date_range
python buzzfeed.py -q $query -r $date_range
