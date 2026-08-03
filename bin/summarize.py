#!/usr/bin/env python

# summarize.py - distill a given text

# Eric Lease Morgan <eric_morgan@infomotions.com>
# (c) Infomotions, LLC; distributed under a GNU Public License

# July 27, 2026 - first cut; at the Culver Coffee Shop


# configure
MODEL        = 'glm-5.2:cloud'
ENDPOINT     = "http://localhost:8000/mcp"
SYSTEMPROMPT = './etc/system-prompt.txt'
RESULTS	     = './etc/results.md'

# require
from asyncio                    import run
from mcp                        import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from ollama                     import chat
from sys                        import argv, exit

# get input
if len( argv ) != 3 : exit( 'Usage: ' + argv[ 0 ] + " <file> <prompt>" )
file   = argv[ 1 ]
prompt = argv[ 2 ]

# get the results
with open( file ) as handle : markdown = handle.read()

with open( SYSTEMPROMPT ) as handle : systemPrompt = handle.read()
systemPrompt = systemPrompt.replace( '##PROMPT##', prompt )

response = chat(
	model=MODEL,
	messages=[
		{ "role": "system", "content": systemPrompt, },
		{ "role": "user", "content": markdown, },
	],
)

# output and done
print(response["message"]["content"])
exit()


