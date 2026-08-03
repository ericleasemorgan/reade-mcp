#!/usr/bin/env python

# call-tool.py - a front-end to the tools of the Reader MCP server

# Eric Lease Morgan <eric_morgan@infomotions.com>
# (c) Infomotions, LLC; distributed under a GNU Public License

# July 27, 2026 - first cut; at the Culver Coffee Shop


# configure
MODEL        = 'glm-5.2:cloud'
ENDPOINT     = "http://localhost:8000/mcp"
SYSTEMPROMPT = './etc/system-prompt.txt'

# require
from asyncio                    import run
from mcp                        import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from ollama                     import chat
from sys                        import argv, exit


# do the work
async def main( carrel, tool, systemPrompt ) :

	async with streamablehttp_client( ENDPOINT ) as ( read, write, _ ):
		async with ClientSession(read, write) as session:
			await session.initialize()
				
			result = await session.call_tool( tool, { 'carrel': carrel } )
			result = result.content[0].text
				
			response = chat(
				model=MODEL,
				messages=[
					{ "role": "system", "content": systemPrompt, },
					{ "role": "user", "content": result, },
				],
			)
			
			print(response["message"]["content"])


# get input
if len( argv ) != 4 : exit( 'Usage: ' + argv[ 0 ] + " <carrel> <tool> <prompt>" )
carrel = argv[ 1 ]
tool   = argv[ 2 ]
prompt = argv[ 3 ]

# build the system prompt
with open( SYSTEMPROMPT ) as handle : systemPrompt = handle.read()
systemPrompt = systemPrompt.replace( '##PROMPT##', prompt )

# on my mark, get set, go
run( main( carrel, tool, systemPrompt ) )
