#!/usr/bin/env python

# ask-alcuin.py - "Alcuin in dead. Long live Alcuin!"; an LLM agent (librarian) intended to be used against the local collection of Distant Reader study carrels

# Eric Lease Morgan <eric_morgan@infomotions.com>
# (c) Infomotions, LLC; distributed under a GNU Public License

# July 29, 2026 - first cut, but rooted in a vibe coding effort
# July 31, 2026 - going through the vibe coding and making my mark


# configure
SERVER            = "/Users/eric/Documents/reader-mcp/bin/server.py"
MODEL             = 'glm-5.2:cloud'
SYSTEMPROMPT      = "Results should be written in the third person. Return results as if they were written by a student attending a liberal arts college. Ask questions, sometimes, but not always. The model is working within a generative-AI system called a RAG, and therefore results are intended to be primarily drawn from the underlying MCP server; results drawn from outside the server are to be kept to a bare minimum. The model is intended to be used as an analysis tool not as an oracle. When citing sentences, include item and idx values. When citing items and/or sentences in HTML files, use getURLToOriginal to hyperlink the items and/or sentences back to the original item. Be sure to text-align:right a signature to the whole HTML file with the name/address of 'Eric Lease Morgan <eric_morgan@infomotions.com>'. If possible, give the HTML today's date."
MAXIMUMITERATIONS = 12
PLACEHOLDERS      = ['##CARREL##', '##CARREL02##', '##CARREL03##', '##CARREL04##']

# require
from asyncio          import run
from json             import dumps
from mcp              import ClientSession
from mcp.client.sse   import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types        import TextContent, TextResourceContents, BlobResourceContents
from ollama           import chat
from re               import match, compile
from sys              import stderr, argv, exit, executable


async def resolve_prompt_resources(session: ClientSession, text: str, resources: list) -> str :
	
	'''Scan text for resource URIs that match known MCP resource schemes. Fetch each one from the MCP server and return the content as context. Non-resource URIs (http, https, etc.) are ignored.'''
	
	# process each source; create a list of local schemes
	schemes = set()
	for resource in resources :
	
		found = match(r"([a-zA-Z]+)://", resource["uri"])
		if found :
			scheme = found.group(1).lower()
			if scheme not in ('http', 'https', 'ftp', 'mailto', 'file') : schemes.add( scheme )
	
	if not schemes : return ''
	
	# Build regex to find URIs with those schemes in the text
	# Matches things like: readme://homer/  or  bibliography://homer/
	scheme_pattern = "|".join( schemes )
	uri_regex = compile(rf"\b({scheme_pattern})://([a-zA-Z0-9_\-/.]+)")
	
	matches = uri_regex.findall(text)
	
	if not matches:
		stderr.write("  (no resource URIs found in prompt)\n")
		return ""
	
	context_parts = []
	seen = set()
	
	for scheme, path in matches:
		uri = f"{scheme}://{path}"
		
		if uri in seen : continue
		seen.add(uri)
		
		stderr.write(f"📄 Found resource URI in prompt: {uri}\n")
		try :
		
			content = await read_resource(session, uri)
			if content :
			
				header = f"[Resource from prompt: {uri}]"
				context_parts.append(f"{header}\n{content}")
				stderr.write(f"✅ Loaded ({len(content)} chars)\n")
				
			else : stderr.write(f"⚠️  Empty response\n")
			
		except Exception as e : stderr.write(f"⚠️  Could not read: {e}\n")
	
	stderr.write(f"  → Resolved {len(context_parts)} prompt resources\n")
	return "\n\n".join(context_parts)


def connect_stdio(server_script: str):

    """Return an async context manager for a stdio MCP server."""
    params = StdioServerParameters( command=executable, args=[server_script] )
    return stdio_client(params)


def connect_sse( url: str ) :

	'''Return an async context manager for an SSE MCP server.'''
	return sse_client(url)


async def discover_resources(session: ClientSession) -> list:

	'''List all resources AND resource templates from the MCP server. Returns a list of dicts with 'uri', 'name', 'description', 'mimeType'.'''
	
	resources = []
	
	# ── Static resources (fixed URIs) ──
	listed = await session.list_resources()
	for r in listed.resources:
		resources.append({
			"uri": str(r.uri),
			"name": r.name or "",
			"description": r.description or "",
			"mimeType": r.mimeType or "text/plain",
			"is_template": False,
		})
	
	# ── Resource templates (parameterized URIs) ──
	templates = await session.list_resource_templates()
	for t in templates.resourceTemplates :  
	
		resources.append({
			"uri": t.uriTemplate,         
			"name": t.name or "",
			"description": t.description or "",
			"mimeType": "text/plain",
			"is_template": True,
		})
	
	return resources


async def read_resource(session: ClientSession, uri: str) -> str:
    """
    Read a single resource from the MCP server and return its text content.
    Handles both text and binary resources.
    """
    result = await session.read_resource(uri)

    if not result.contents: return ""

    content = result.contents[0]

    if isinstance(content, TextResourceContents): return content.text

    elif isinstance(content, BlobResourceContents):
        return f"[Binary resource: {len(content.blob)} bytes, mime: {content.mimeType}]"

    return str(content)


async def load_all_resources(session: ClientSession) -> str:
    """
    Discover and read all static (non-template) resources from the
    MCP server. Returns formatted context text for injection into the prompt.
    """
    resources = await discover_resources(session)

    if not resources:
        print("  (no resources available on this server)")
        return ""

    context_parts = []
    loaded_count = 0

    for r in resources:
        if r["is_template"]:
            stderr.write(f"📋 Template found (needs params): {r['uri']}\n")
            continue

        print(f"📄 Reading: {r['uri']}")
        text = await read_resource(session, r["uri"])

        if text:
            header = f"[Resource: {r['uri']}]"
            if r["name"]:
                header += f" — {r['name']}"
            context_parts.append(f"{header}\n{text}")
            loaded_count += 1

    stderr.write(f"  → Loaded {loaded_count} resources\n")
    return "\n\n".join(context_parts)


# ═══════════════════════════════════════════════════════════════
# Tool discovery + execution
# ═══════════════════════════════════════════════════════════════

async def discover_tools(session: ClientSession) -> list[dict]:
    """
    List all tools from the MCP server and convert them to
    Ollama's tool format.
    """
    result = await session.list_tools()

    ollama_tools = []
    for tool in result.tools:
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                },
            },
        })

    return ollama_tools


async def execute_tool(session: ClientSession, tool_name: str, arguments: dict) -> str:
    """
    Call a tool on the MCP server and return its text output.
    """
    result = await session.call_tool(tool_name, arguments)

    if result.isError :  
                            
        error_msg = result.content[0].text if result.content else "Unknown error"
        return f"Tool error: {error_msg}"

    if not result.content : return "No result"

    outputs = []
    for block in result.content:
        if isinstance(block, TextContent):
            outputs.append(block.text)
        else:
            outputs.append(str(block))

    return "\n".join(outputs)

# the agent
async def run_agent( session: ClientSession, user_question: str, model: str = MODEL, max_iterations: int = 8 ) :

	'''Flow: 1. Discover + load MCP resources → inject as context, 2. Discover MCP tools → make available to the LLM, 3. Agent loop: Ollama calls tools as needed, we execute via MCP, 4. Model generates final interpretation using all sources'''

	# load resources
	stderr.write("📥 Discovering MCP resources...\n")
	resource_context = await load_all_resources(session)
	
	stderr.write("🔎 Scanning prompt for resource URIs...\n")
	resources = await discover_resources(session)
	prompt_resource_context = await resolve_prompt_resources(session, user_question, resources)
	
	# Combine both sources of context
	all_context = "\n\n".join( part for part in [ resource_context, prompt_resource_context ] if part )
	
	# find tools
	stderr.write("🔧 Discovering MCP tools...\n")
	tools = await discover_tools( session )
	
	if tools :
		for tool in tools : desc = tool["function"]["description"][:80]
	else : stderr.write("  (no tools available on this server)\n")
	
	# build a conversation
	system_prompt = SYSTEMPROMPT
	
	if all_context :
	
		user_content = (
		
			f"The following context data is available from connected sources:\n"
			f"\n{'─' * 60}\n"
			f"{all_context}\n"
			f"{'─' * 60}\n"
			f"\nQuestion: {user_question}"
			
		)
	else : user_content = user_question
	
	messages = [ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_content} ]
	
	# make the agent go
	stderr.write(f"🤖 Running agent\n\n")
	for iteration in range(1, max_iterations + 1) :
	
		# submit a chat and update the messages
		stderr.write(f"── Iteration {iteration} ──\n")
		response = chat( model=model, messages=messages, tools=tools if tools else None, stream=False )
		messages.append( response["message"] )
	
		tool_calls = response[ "message" ].get( "tool_calls" )
	
		# done, conditionally
		if not tool_calls :
		
			#stderr.write(f"\n{'═' * 70}\n")
			stderr.write("Done.\n")
			#stderr.write(f"{'═' * 70}\n")
			print(response["message"]["content"] )
			#stderr.write(f"\n{'═' * 70}\n")
	
			tool_calls_made = sum( 1 for m in messages if m.get("role") == "tool" )
			stderr.write(f"\n📊 Summary:\n")
			stderr.write(f"   Tool calls made:  {tool_calls_made}\n")
			stderr.write(f"   Total messages:   {len(messages)}\n")
			stderr.write(f"   Iterations:       {iteration}\n")
			return
	
		for call in tool_calls :
		
			tool_name = call["function"]["name"]
			tool_args = call["function"]["arguments"]
	
			stderr.write(f"🔧 Calling: {tool_name}({dumps(tool_args)})\n")
	
			result = await execute_tool( session, tool_name, tool_args )
	
			#preview = result[:200] + ("..." if len(result) > 200 else "")
			#stderr.write(f"     → {preview}\n")
	
			# update
			messages.append( { "role": "tool", "tool_name": tool_name, "content": str( result ) } )
	
		stderr.write( '\n' )
	
	stderr.write("⚠️  Max iterations reached without a final answer.\n")


# main
async def main( prompt ) :

	# initialize connection
	#transport = connect_sse( SERVER )
	transport = connect_stdio( SERVER )

	async with transport as ( read, write ) :
	
		async with ClientSession( read, write ) as session :
			
			await session.initialize()
	
			stderr.write( "✅ Connected to MCP server\n" )
			
			await run_agent( session=session, user_question=prompt, model=MODEL, max_iterations=MAXIMUMITERATIONS )
	

# go
if __name__ == "__main__":

	# get input
	if len( argv ) <= 1 : exit( 'Usage: ' + argv[ 0 ] + " <file> [<carrel> <another carrel> <a third carrel>...]" )
	file    = argv[ 1 ]
	carrels = argv[ 2: ]
		
	# read the prompt
	with open ( file ) as handle : prompt = handle.read()

	# update the prompt; tricky
	for index, carrel in enumerate( carrels ) :
	
		# (re-)initialize
		if index == 0 : placeholder = '##CARREL##'
		else          : placeholder = f'##CARREL{index+1:02d}##'
		
		# update
		prompt = prompt.replace( placeholder, carrel )
		
	# now actually go
	run( main( prompt ) )
