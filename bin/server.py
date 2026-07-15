#!/usr/bin/env python

# server.py - a Distant Reader MCP server

# Eric Lease Morgan <eric_morgan@infomotions.com>
# (c) Infomotions, LLC; distributed under a GNU Public License

# April 27, 2026 - first cut
# April 28, 2026 - added unigrams; this is working!
# April 29, 2026 - added sentences and rdr.keywords
# May    3, 2026 - added a few more tools and associated prompts; I don't think resources work
# May    7, 2026 - added even more tool; this is really working very well
# May    8, 2026 - added get full path to original items
# May   11, 2026 - cleaned up naming conventions; works the same though
# May   15, 2026 - refined inline to expose interesting, POS, and entity words; limite results to segments of lists
# May   24, 2026 - refined the documentation regarding items; works better
# May   25, 2026 - added getAuthors, getTitles, and getDates
# May   28, 2026 - refined getSentencesWord
# June   2, 2026 - removed getSentencesWord; too complicated
# June   9, 2026 - after using a larger underneath model, restored getSentencesWord; kewl
# June  17, 2026 - added additional local URLs
# June  22, 2026 - added some refactoring bits as suggestet by an LLM; hmmm.
# July  14, 2026 - add save to a file; at the cabin


# configure
NAME	= 'Distant Reader MCP Server'
LIBRARY = 'localLibrary'
TXT	    = 'txt'
MODEL   = 'locusai/multi-qa-minilm-l6-cos-v1'
MAXIMUM = 4096
HTML    = 'reader-results.html'


# require
from json			    import loads
from mcp.server.fastmcp import FastMCP
from ollama	            import embed
from pandas	            import DataFrame, read_csv
from sqlite_vec         import load
from sqlite3	        import connect
from struct			    import pack
from typing			    import List, Literal
from pathlib            import Path
import rdr


# serializes a list of floats into a compact "raw bytes" format; makes things more efficient?
def serialize( vector: List[float]) -> bytes : return pack( "%sf" % len( vector ), *vector )


# normalize strings by replacing unicode hyphens with standard ascii hyphens
def normalize( value: str ) -> str : return value.replace( '‑', '-' )


# helper to fetch specific bibliographic fields to reduce code repetition
def _fetch_bib_field( carrel: str, field: str ) -> str:
	carrel   = normalize( carrel )
	results  = []
	try:
		bibliography = loads( rdr.bibliography( carrel, format='json' ) )
		for item in bibliography :
			# ensure the ID is always present, and gracefully handle missing fields
			entry = { 'id': item.get( 'id', 'unknown' ) }
			entry[ field ] = item.get( field, 'Not available' )
			results.append( entry )
		return str( results )
	except Exception as e:
		return f"Error retrieving {field} from {carrel}: {str(e)}"


# helper to construct and validate file URLs to reduce code repetition
def _get_url( carrel: str, item: str, folder: str, extension: str ) -> str:
	carrel = normalize( carrel )
	item   = normalize( item )
	try:
		for record in loads( rdr.bibliography( carrel, format='json' ) ) :
			if record[ 'id' ] == item :
				if folder == rdr.CACHE : fullpath = 'file://' + str( library/carrel/folder/( item + record[ 'extension' ] ) )
				else               : fullpath = 'file://' + str( library/carrel/folder/( item + extension ) )
				return fullpath
		return "That item was not found, are you sure the identifier's value is correct?"
	except Exception as e:
		return f"Error retrieving URL: {str(e)}"


# initailize
server  = FastMCP( NAME, json_response=True, stateless_http=True )
library = rdr.configuration( LIBRARY )



############## save to file ##############

@server.tool()
def save_HTML( content: str ) -> str:
    '''Save the given HTML to a file'''
        
    html = Path.cwd()/HTML
    try:
        with open( html, "w", encoding="utf-8") as handle : handle.write( content )
        return f"Successfully wrote {len(content)} characters to file://{html}"
    
    # alas
    except Exception as error : return f"Error: {error}"


############## words in sentences ##############

@server.tool()
def getSentences( carrel:str, query:str ) -> str :
	"""
		Output all sentences from the given carrel which contains or are semantically simlar to the given word . The resulting sentences are useful for sentences level analysis across the entire carrel.
		Args:
			carrel (str): The name of a carrel.
			query (str): An individual word or phase
		Returns:
			str: a new-line delimited list of sentences
	"""

	carrel   = normalize( carrel )
	depth    = len( rdr.concordance(carrel, localLibrary=None, query=query.lower()) )

	DATABASE = 'sentences.db'
	COLUMNS  = [ 'item', 'idx', 'sentence' ]
	SELECT   = "SELECT title AS 'item', idx, sentence, VEC_DISTANCE_L2(embedding, ?) AS distance FROM sentences ORDER BY distance LIMIT ?"	
	database = connect( rdr.configuration( LIBRARY )/carrel/(rdr.ETC)/DATABASE )
	database.enable_load_extension( True )
	load( database )

	# vectorize query and search; get a set of matching records
	query   = embed( model=MODEL, input=query ).model_dump( mode='json' )[ 'embeddings' ][ 0 ]
	records = database.execute( SELECT, [ serialize( query ), depth ] ).fetchall()

	# process each record; create a list of sentences
	sentences = []
	for index, record in enumerate( records ) :
	
		# parse
		title	 = record[ 0 ]
		idx	     = record[ 1 ]
		sentence = record[ 2 ]
		distance = record[ 3 ]
		
		# short-circuit
		if index > MAXIMUM : break
		
		# update
		sentences.append( [ title, idx, sentence ] )
	
	# create a dataframe of the sentences and sort by title
	sentences = DataFrame( sentences, columns=COLUMNS )
	return( sentences.to_json( orient='index' ) )

@server.prompt()
def p_getSentences( carrel:str, query:str ) :
	'''Return the sentences including or semantically similar to the given word or phrase from the given carrel'''
	return( f'''Given the carrel named '{carrel}' list all of the sentences including or are semantically similar to the word or phrase '{query}'.''' )


############## rdr.pos: pronouns ##############

@server.tool()
def getPronouns( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of of all the pronouns identified as a part-of-speech value. These are POS words. This process helps identify who and what is included in the text.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of pronouns from the given carrel
	'''
	carrel     = normalize( carrel )
	adjectives = rdr.pos(carrel, select='lemma', like='PRON', count=True ).splitlines()
	segment    = len( adjectives ) // 4
	return( str( adjectives[ :segment ] ) )

@server.prompt()
def p_getPronouns( carrel:str ) :
	'''Get all pronouns from the given carrel and extracted from the parts-of-speech process'''
	return( f'''Given the carrel named '{carrel}', return a frequency list of all the pronous.''' )


############## rdr.pos: adjectives ##############

@server.tool()
def getAdjectives( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of of all the adjectives identified as a part-of-speech value. These are POS words. This process helps identify how the things in the carrel are described.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of adjectives from the given carrel
	'''
	carrel     = normalize( carrel )
	adjectives = rdr.pos(carrel, select='lemma', like='ADJ', count=True ).splitlines()
	segment    = len( adjectives ) // 4
	return( str( adjectives[ :segment ] ) )

@server.prompt()
def p_getAdjectives( carrel:str ) :
	'''Get all adjectives from the given carrel and extracted from the parts-of-speech process'''
	return( f'''Given the carrel named '{carrel}', return a frequency list of all the adjectives.''' )


############## full path to origial document ##############

@server.tool()
def getURLToOriginal( carrel: str, item:str ) -> str:
	'''
		Given the name of a carrel and an identifier in the carrel, output a local, file-based (file://) URL pointing to an item in the carrel. This is a bibliographic.
		Args:
			carrel (str): the name of a study carrel
			item (str): the name of an item in the study carrel
		Returns: 
			str: a URL pointing to the original item in the study carrel
	'''
	return _get_url( carrel, item, rdr.CACHE, '' )

@server.prompt()
def p_getURLToOriginal( carrel:str, item: str ) :
	'''The the full path to the original version of the given item in the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the full path to the original version of '{item}'.''' )


############## full path to origial document ##############

@server.tool()
def getURLToHtm( carrel: str, item:str ) -> str:
	'''
		Given the name of a carrel and an identifier in the carrel, output a local, file-based (file://) URL pointing to an HTML version of the original item. This is a bibliographic.
		Args:
			carrel (str): the name of a study carrel
			item (str): the name of an item in the study carrel
		Returns: 
			str: a URL pointing to an HTML version of the item in the study carrel
	'''
	return _get_url( carrel, item, 'htm', '.htm' )

@server.prompt()
def p_getURLToHtm( carrel:str, item: str ) :
	'''The the full path to the HTML version of the given item in the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the URL to the HTML version of '{item}'.''' )


############## full path to origial document ##############

@server.tool()
def getURLToTxt( carrel: str, item:str ) -> str:
	'''
		Given the name of a carrel and an identifier in the carrel, output a local, file-based (file://) URL pointing to the plain text version of the original item. This is a bibliographic.
		Args:
			carrel (str): the name of a study carrel
			item (str): the name of an item in the study carrel
		Returns: 
			str: a URL pointing to a plain text version of the item in the study carrel
	'''
	return _get_url( carrel, item, TXT, '.txt' )

@server.prompt()
def p_getURLToTxt( carrel:str, item: str ) :
	'''The the full path to plain text version of the given item in the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the URL to the plain text version of '{item}'.''' )


############## rdr.pos: verbs ##############

@server.tool()
def getVerbs( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of of all the lemmatized verbs identified as a part-of-speech value.  These are POS words. This process helps identify what the things in this carrel do; what actions do they take.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of lemmatized verbs form the given carrel
	'''
	carrel  = normalize( carrel )
	verbs   = rdr.pos(carrel, select='lemma', like='VERB', count=True )
	segment = len( verbs ) // 4
	return( str( verbs[ :segment ] ) )

@server.prompt()
def p_getVerbs( carrel:str ) :
	'''Get all lemmatized verbs from the given carrel as extracted from the parts-of-speech process'''
	return( f'''Given the carrel named '{carrel}', return the lemmatized part-of-speech value of VERB.''' )


############## bibliographics: titles ##############

@server.tool()
def getTitles( carrel: str ) -> str:
	'''
		Given the name of a carrel output a list of all the titles of items in the given carrel. This is a bibliographic. This addresses the question, "What are the titles of the items in this carrel?"
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a list of titles and the item identifiers from the given carrel
	'''
	return _fetch_bib_field( carrel, 'title' )

@server.prompt()
def p_getTitles( carrel:str ) :
	'''Get all the titles and the associated item identifiers from the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the titles and the item identifiers pointing to the titles of things written  in given carrel.''' )


############## bibliographics: titles ##############

@server.tool()
def getSummaries( carrel: str ) -> str:
	'''
		Given the name of a carrel output a list of all items' summaries as well as their item identifiers. This is a bibliographic. This addresses the question, "What are the items in the carrel about?"
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a list of abstracts and the item identifiers from the given carrel
	'''
	return _fetch_bib_field( carrel, 'summary' )

@server.prompt()
def p_getSummaries( carrel:str ) :
	'''Get all the summaries and the associated item identifiers from the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the summaries and the item identifiers pointing to the titles of things written  in given carrel.''' )


############## bibliographics: authors ##############

@server.tool()
def getAuthors( carrel: str ) -> str:
	'''
		Given the name of a carrel output a list of all the authors of items in the given carrel. These are creators, and this is a bibliographic. This addresses the question, "Who wrote the items in the given carrel?"
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a list of author names and the item identifiers from the given carrel
	'''
	return _fetch_bib_field( carrel, 'author' )

@server.prompt()
def p_getAuthors( carrel:str ) :
	'''Get all the authors and the associated item identifiers from the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the authors and the item identifiers pointing to the things they wrote in the carrel.''' )


############## bibliographics: dates ##############

@server.tool()
def getDates( carrel: str ) -> str:
	'''
		Given the name of a carrel output a list of all the dates of items in the given carrel. These are dates, and this is a bibliographic. This addresses the question, "When were the thing in this carrel written?"
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a list of date and the item identifiers from the given carrel
	'''
	return _fetch_bib_field( carrel, 'date' )

@server.prompt()
def p_getDates( carrel:str ) :
	'''Get all the dates of the items written and the associated item identifiers from the given carrel'''
	return( f'''Given the carrel named '{carrel}', return the dates and the item identifiers pointing to the things in the carrel.''' )


############## rdr.pos: nouns ##############

@server.tool()
def getNouns( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of of all the nouns identified as a part-of-speech value. These are POS words. This helps identify what it mentioned in the given carrel.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of nouns from the given carrel
	'''
	carrel  = normalize( carrel )
	nouns   = rdr.pos(carrel, select='words', like='NOUN', count=True ).splitlines()
	segment = len( nouns ) // 16
	return( str( nouns[ :segment ] ) )

@server.prompt()
def p_getNouns( carrel:str ) :
	'''Get all nouns from the given carrel and extracted from the parts-of-speech process'''
	return( f'''Given the carrel named '{carrel}', return part-of-speech of type NOUN.''' )


############## named-entitites: people ##############

@server.tool()
def getPeople( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of people identified as a named entity. This helps identify who is mentioned in the carrel. These are ENTITY words.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of people form the given carrel
	'''
	carrel  = normalize( carrel )
	people  = rdr.entities(carrel, select='entity', like='PERSON', count=True ).splitlines()
	segment = len( people ) // 8
	return( str( people[ :segment ] ) )

@server.prompt()
def p_getPeople( carrel:str ) :
	'''Get all names of people from the given carrel and extracted from the named entity process'''
	return( f'''Given the carrel named '{carrel}', return named rdr.entities of type PERSON.''' )


############## named-entitites: ORG ##############

@server.tool()
def getOrganizations( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of organizations identified as a named entity. This helps identify what groups of people are mentioned in the carrel. These are ENTITY words.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of organizations form the given carrel
	'''
	carrel        = normalize( carrel )
	organizations = rdr.entities (carrel, select='entity', like='ORG', count=True ).splitlines()
	segment       = len( organizations ) // 2
	return( str( organizations[ :segment ] ) )

@server.prompt()
def p_getOrganizations( carrel:str ) :
	'''Get all names of organizations from the given carrel and extracted from the named entity process'''
	return( f'''Given the carrel named '{carrel}', return named rdr.entities of type ORG.''' )


############## named-entitites: GPE ##############

@server.tool()
def getPlaces( carrel: str ) -> str:
	'''
		Given the name of a carrel output a frequency list of places (geo-political rdr.entities) identified as a named entity. This helps identify what places are mentioned in the carrel. These are ENTITY words.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a tab-delinmited list of places form the given carrel
	'''
	carrel  = normalize( carrel )
	places  = rdr.entities (carrel, select='entity', like='GPE', count=True ).splitlines()
	segment = len( places ) // 2
	return( str( places[ :segment ] ) )

@server.prompt()
def p_getPlaces( carrel:str ) :
	'''Get all names of geo-political rdr.entities (places) from the given carrel and extracted from the named entity process'''
	return( f'''Given the carrel named '{carrel}', return named rdr.entities of type GPE.''' )


############## item identifiers ##############

@server.tool()
def getItems( carrel: str ) -> str:
	'''
		Given the name of a carrel output a list of all the item identifiers
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a list of all the items's identifiers
	'''
	carrel       = normalize( carrel )
	bibliography = loads( rdr.bibliography( carrel, format='json' ) )
	return( str( [ item[ 'id' ] for item in bibliography ] ) )

@server.prompt()
def p_getItems( carrel:str ) :
	'''Get all item identifiers from a given carrel'''
	return( f'''Given the carrel named '{carrel}', return all item identifiers it contains.''' )


############## plain text ##############

@server.tool()
def getPlaintext( carrel: str, item:str ) -> str:
	'''
		Given the name of a carrel and an item identifier, return the plain text of the item. The result is useful for analysis of the resulting text.
		Args:
			carrel (str): the name of a study carrel
			item (str): an item identifier pointing to an specific item in the carrel
		Returns: 
			str: the plain text of the given item
	'''
	carrel = normalize( carrel )
	item   = item.replace( '‑', '-' )
	with open( library /carrel/TXT/(item + '.txt' ) ) as handle : plaintext = handle.read()
	return( plaintext )

@server.prompt()
def p_getPlaintext( carrel:str, item:str ) :
	'''Retrieve the plain text version of an item from a carrel'''
	return( f'''Given the carrel named '{carrel}' and the identifier '{item}', get the plain text version of the item.''' )



############## rdr.keywords from carrel ##############

@server.tool()
def getKeywords( carrel:str ) -> str :
	"""
		Count and tabulate the rdr.keywords associated with the given study carrel. This process addresses the questions, "What sorts of things are discussed in this carrel?" or "What is the carrel about?"
		Args:
			carrel (str): The name of a carrel.
		Returns:
			str: a tab-delimited list of carrel rdr.keywords and their associated frequencies
	"""
	carrel = normalize( carrel )
	return( rdr.keywords( carrel, count=True ) )

@server.prompt()
def p_getKeywords( carrel:str ) :
	"""Count and tabulate the rdr.keywords associated with the given study carrel"""
	return f"""Given the carrel named '{carrel}', count and tabulate the rdr.keywords."""

############## semantically similar words ##############

@server.tool()
def getSimilarWords( carrel:str, word:str, depth:int=16 ) -> str :
	"""
		Given the name of a study carrel and a word, outut the depth number of semantically similar words as well as their associated scores.
		Args:
			carrel (str): The name of a carrel.
			word (str): A word use to find similarity on
			depth (int): The number of words to return
		Returns:
			str: a tab-delimited list of semantically similar words and their associated distance scores
	"""
	carrel = normalize( carrel )
	return( rdr.word2vec( carrel, type='similarity', query=word, topn=depth ) )

@server.prompt()
def p_getSimilarWords( carrel:str, word:str, depth:int ) :
	"""From the given carrel, word, and depth, count and tabulate the semantically simlar words"""
	return f"""Given the carrel named '{carrel}', count and tabulate the semantically simlar to '{word}' and limit the output to '{depth}' words."""


############## ungrams ##############

@server.tool()
def getUnigrams( carrel:str ) -> str :
	"""
		Outputs the counts and tabulations of individual words (unigrams) in the given carrel. This process addresses the question "What sorts of things are discussed in this carrel?"
		Args:
			carrel (str): The name of a carrel.
		Returns:
			str: a list of the carrel's most frequent unigrams
	"""
	carrel   = normalize( carrel )
	unigrams = rdr.ngrams( carrel, size=1, count=True ).splitlines()
	segment  = len( unigrams ) // 16
	return( str( unigrams[ :segment ] ) )

@server.prompt()
def p_getUnigrams( carrel:str, size:int ) :
	"""Count & tabulate individual words (unigrams) in the given carrel"""
	return f"""Given the carrel named '{carrel}', count and tabulate the most frequent individual words (unigrams)."""


############## bigrams ##############

@server.tool()
def getBigrams( carrel:str ) -> str :
	"""
		Outputs the counts and tabulations of the two-word phrases (bigrams) from the given carrel. This process addresses the question "What sorts of things are discussed in this carrel?"
		Args:
			carrel (str): The name of a carrel.
		Returns:
		str: a list of the carrel's most frequent bigrams
	"""
	carrel  = normalize( carrel )
	bigrams = rdr.ngrams( carrel, size=2, count=True ).splitlines()
	segment = len( bigrams ) // 32
	return( str( bigrams[ :segment ] ) )

@server.prompt()
def p_getBigrams( carrel:str ) :
	"""Count & tabulate two-word phrases (bigrams) in the given carrel"""
	return f"""Given the carrel named '{carrel}', count and tabulate the most frequent two-word phrases (bigrams)."""


############## catalog ##############

@server.tool()
def getCarrels() -> str :
	"""
		Output the list of study carrels available from the local library.
		Returns:
			str: a list of the carrels accessible from the local library
	"""
	return( rdr.catalog() )

@server.prompt()
def p_getCarrels() :
	"""Get a list of the carrels available in the local library"""
	return( f"""In the form of a paragraph, list the carrels available from the local library.""" )


############## bibliography ##############

@server.tool()
def getBibliography( carrel: str ) -> str:
	"""
		Output the bibliographic metadata elements (author, title, date, summary, rdr.keywords, flesch score, and number of words) for the given carrel.
		Args:
			carrel (str): The name of a carrel.
		Returns:
			str: a JSON stream including an identifier, author, title, date, summary, rdr.keywords, Flesch (readability) score, and number of words.
	"""
	carrel = normalize( carrel )
	return( rdr.bibliography( carrel, format='json' ) )

@server.prompt()
def p_getBibliography( carrel:str ) :
	"""Given the name of a carrel, output the bibliographic elements of each item in the carrel"""
	return( f"""Given the carrel named '{carrel}', output the identifier, author, title, date, summary, rdr.keywords, Flesch (readability) score, and size measure in words for each item in the carrel.""" )


############## extent of carrel in words ##############

@server.tool()
def getSizeInWords( carrel:str ) -> int:
	"""
		Given the name of a study carrel return the size of the carrel measured in number of words. This is an extent.
		Args:
			carrel (str): The name of a local Distant Reader study carrel.
		Returns:
			int: a number denoting the size of the carrel measured in words
	"""
	carrel = normalize( carrel )
	return( rdr.extents( carrel, 'words' ) )

@server.prompt()
def p_getSizeInWords( carrel:str ) :
	"""Get the size of the given carrel measured in total number of words"""
	return f"""Return the size of '{carrel}' measured in total number of words."""


############## extent of carrel in items ##############

@server.tool()
def getSizeInItems( carrel:str ) -> int:
	"""
		Given the name of a study carrel return number of items in the carrel. This is an extent.
		Args:
			carrel (str): The name of a local Distant Reader study carrel.
		Returns:
			int: a number denoting the size of the carrel measured in number of items
	"""
	carrel = normalize( carrel )
	return( rdr.extents( carrel, 'items' ) )

@server.prompt()
def p_getSizeInItems( carrel:str ) :
	"""Get the size (extent) of the given carrel measured in total number of items"""
	return f"""Return the size of '{carrel}' measured in total number of items."""


############## extent of carrel in items ##############

@server.tool()
def getSizeInFlesch( carrel:str ) -> int:
	"""
		Given the name of a study carrel return the overall Flesch Readability score of the carrel. This is an extent.
		Args:
			carrel (str): The name of a local Distant Reader study carrel.
		Returns:
			int: the Flesch Readability Score for the given carrel
	"""
	carrel     = normalize( carrel )
	return( rdr.extents( carrel, 'flesch' ) )

@server.prompt()
def p_getSizeInFlesch( carrel:str ) :
	"""Get the Flesh Readability score of the given carrel."""
	return f"""Return the overall Flesch Readability Score (extent) of '{carrel}'."""


############## resources, but I don't think they work ##############

@server.resource( "tm://{carrel}/" )
def r_tm( carrel: str ) -> str:

	TOPICMODEL  = 'etc/topic-model/keys.tsv'
	COLUMNS     = [ 'labels', 'weights', 'features' ]
	
	# read and sort keys file
	keys = read_csv( library/carrel/TOPICMODEL, sep='\t', names=COLUMNS )
	keys.sort_values( by='weights', ascending=False, inplace=True )
	
	# create labels for each topic
	labels = []
	for index, row in keys.iterrows() :
	
		# parse
		features = row[ 'features' ].split()
	
		# loop through each feature
		for feature in features :
	
			# build the list, conditionally
			if feature in labels : continue
			labels.append( feature )
			break
	
	# add the labels, rearrange (just for fun)
	keys[ 'labels' ] = labels
	keys = keys[ [ 'labels', 'weights', 'features' ] ]
	
	return( keys.to_csv( index=False ) )

############## resources, but I don't think they work ##############

@server.resource( "gml://{carrel}/" )
def r_gml( carrel: str ) -> str:
	'''
		Given the name of a carrel output an JSON file of bibliographics.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a JSON file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.gml' ) ) as handle : gml = handle.read()
	return( gml )

@server.resource( "summary://{carrel}/" )
def r_summary( carrel: str ) -> str:
	'''
		Given the name of a carrel output an JSON file of bibliographics.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a JSON file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.htm' ) ) as handle : summary = handle.read()
	return( summary )

@server.resource( "analysis://{carrel}/" )
def r_analysis( carrel: str ) -> str:
	'''
		Given the name of a carrel output an JSON file of bibliographics.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a JSON file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.html' ) ) as handle : about = handle.read()
	return( about )

@server.resource( "bibliography://{carrel}/json/" )
def r_bibliographyJson( carrel: str ) -> str:
	'''
		Given the name of a carrel output an JSON file of bibliographics.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a JSON file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.json' ) ) as handle : json = handle.read()
	return( json )

@server.resource( "bibliography://{carrel}/txt/" )
def r_bibliographyTxt( carrel: str ) -> str:
	'''
		Given the name of a carrel output an JSON file of bibliographics.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a JSON file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.txt' ) ) as handle : txt = handle.read()
	return( txt )

@server.resource( "rdf://{carrel}/" )
def r_rdf( carrel: str ) -> str:
	'''
		Given the name of a carrel output an RDF/XML representation of the carrel's bibliographics, if it exists.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: an RDF/XML file
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.rdf' ) ) as handle : rdf = handle.read()
	return( rdf )

@server.resource( "csv://{carrel}/" )
def r_csv( carrel: str ) -> str:
	'''
		Given the name of a carrel output the metadata used to create the carrel in the first place, if it exists.
		Args:
			carrel (str): the name of a study carrel
		Returns: 
			str: a comma-separated values (CSV) stream of metadata
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/( 'index.csv' ) ) as handle : csv = handle.read()
	return( csv )

@server.resource( "plaintext://{carrel}/{item}" )
def r_plaintext( carrel: str, item: str ) -> str:
	'''
		Given the name of an item in a carrel, return the plain text of the item
		Args:
			carrel (str): the name of a study carrel
			item (str): the name of item in the carrel
		Returns: 
			str: a plain text stream of the item
	'''
	with open( ( rdr.configuration( LIBRARY ) )/carrel/'txt'/( item + '.txt' ) ) as handle : text = handle.read()
	return( text )


@server.resource("readme://{carrel}/")
def r_readme( carrel: str ) -> str:
	"""Use this resource to get a README file what the Distant Reader and study carrels are."""
	with open ( (rdr.configuration( LIBRARY ) )/carrel/( 'readme.txt' ) ) as handle : data = handle.read()
	return( data )


# go
if __name__ == "__main__" :

	#server.run( transport="streamable-http" )
	server.run( transport="stdio" )

