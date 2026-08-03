#!/usr/bin/env bash

# agent.sh - a rudimentary front-end used to query reader-mcp

# Eric Lease Morgan <eric_morgan@infomotions.com>
# (c) Infomotions, LLC; distributed under a GNU Public License

# July 26, 2026 - first cut; last day at the cabin


# configure
SCRIPT='./etc/script.tsv'
RESOURCES='./bin/get-resource.py'
TOOLS='./bin/call-tool.py'
RESULTS='./etc/results.md'
SUMMARIZE='./bin/summarize.py'

# make sane
rm -rf $RESULTS
touch $RESULTS

# get and process each of the given commands
IFS=$'\t'
cat $SCRIPT | while read VERB CARREL CONTENT HEADER PROMPT; do

	# debug
	echo "     verb: $VERB"    >&2
	echo "   carrel: $CARREL"  >&2
	echo "  content: $CONTENT" >&2
	echo "   header: $HEADER"  >&2
	echo "   prompt: $PROMPT"  >&2
	echo                       >&2
	
	# oupt a header
	echo -e "\n# $HEADER\n" >> $RESULTS

	# do the work; resources
	if [[ $VERB == 'resource' ]]; then $RESOURCES $CONTENT '$PROMPT' >> $RESULTS
		
	# tools
	elif [[ $VERB == 'tool' ]]; then $TOOLS $CARREL $CONTENT '$PROMPT' >> $RESULTS

	# write
	elif [[ $VERB == 'write' ]]; then cat $CONTENT >> $RESULTS

	# summarize
	elif [[ $VERB == 'summarize' ]]; then $SUMMARIZE $CONTENT $PROMPT >> $RESULTS

	# error
	else echo -e "Unknown value for type ($VERB). Call Eric.\n" >&2
		
	fi
		
done

# output and done
echo "Done" >&2
cat $RESULTS
exit
