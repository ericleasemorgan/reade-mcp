#!/usr/bin/env python

# configure
ENDPOINT   = "http://localhost:8000/mcp"
MODEL      = 'glm-5.2:cloud'
PROMPT     = 'You are a helpful assistant. List and summarize the following text.'

# require
from asyncio                    import run
from mcp                        import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sys                        import stdout
from ollama                     import chat

# do the work
async def main() :

	async with streamablehttp_client( ENDPOINT ) as ( read, write, _ ) :
	
		async with ClientSession( read, write ) as session :
		
			await session.initialize()
			
			tools = await session.list_tools()
			tools = tools.model_dump_json() 

			print( tools )
			
			#response = chat(
			#	model=MODEL,
			#	messages=[
			#		{ "role":"system", "content":PROMPT, },
			#		{ "role":"user",   "content":tools, },
			#	],
			#)
			
			#print(response["message"]["content"])

# on my mark, get set, go
run( main() )
