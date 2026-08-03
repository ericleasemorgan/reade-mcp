#!/usr/bin/env python

# configure
MODEL        = 'glm-5.2:cloud'
ENDPOINT     = "http://localhost:8000/mcp"
SYSTEMPROMPT = './etc/system-prompt.txt'

# require
from asyncio                    import run
from mcp                        import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic                   import AnyUrl
from ollama                     import chat
from sys                        import argv, exit, stderr

# do the work
async def main( resource, systemPrompt ):
	async with streamablehttp_client( ENDPOINT ) as (read, write, _ ):
		async with ClientSession(read, write) as session:
			await session.initialize()
	
			result = await session.read_resource( AnyUrl( resource ) )
			result = result.contents[0].text
			
			response = chat(
				model=MODEL,
				messages=[
					{ "role": "system", "content": systemPrompt, },
					{ "role": "user", "content": result, },
				],
			)
			
			print(response["message"]["content"])


# get input
if len( argv ) != 3 : exit( 'Usage: ' + argv[ 0 ] + " <resource> <prompt>" )
resource = argv[ 1 ]
prompt   = argv[ 2 ]

# build the system prompt
with open( SYSTEMPROMPT ) as handle : systemPrompt = handle.read()
systemPrompt = systemPrompt.replace( '##PROMPT##', prompt )

# go
run( main( resource, systemPrompt ))
