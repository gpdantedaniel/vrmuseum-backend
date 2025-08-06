import os
import json
import urllib.request
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from neo4j import GraphDatabase
import chromadb
from openai import AzureOpenAI

load_dotenv()

# ========== Neo4J Utilities ==========

CYPHER_QUERY = """
MATCH (a:Specimen)
WHERE a.Specimen = $specimen_name
MATCH (a)-[r]->(m)
WHERE type(r) IN [
    "AT_GROWTH_STAGE",
    "BONE_IS",
    "DURING",
    "FROM_ERA",
    "KERATIN_ON",
    "LIVES_IN_HABITAT",
    "MADE_OF",
    "MUSEUM_ACQUISITION",
    "ORIGINATED",
    "PRESERVED",
    "TEETH_ARE",
    "TYPE_OF",
    "TYPE_OF_HIGH",
    "TYPE_OF_MID"
]
WITH a, collect(DISTINCT m) AS metadata
UNWIND metadata AS m
MATCH (m)<-[:AT_GROWTH_STAGE|BONE_IS|DURING|FROM_ERA|KERATIN_ON|LIVES_IN_HABITAT|MADE_OF|MUSEUM_ACQUISITION|ORIGINATED|PRESERVED|TEETH_ARE|TYPE_OF|TYPE_OF_HIGH|TYPE_OF_MID]-(rec:Specimen)
WHERE rec <> a
WITH rec, count(DISTINCT m) AS score
RETURN rec.Specimen AS recommended_name
ORDER BY score DESC
LIMIT 5
"""

# ========== Prompts ==========

SUMMARIZE_PROMPT = """A user is searching in a virtual museum. 
The user asked the following search query: {query}
Here are the results that were retrieved: {retrieval}
Generate a friendly sentence that acknowledges the query 
and reminds the user of what they might be interested in."""

RESULT_PROMPT = """A user is searching in a virtual museum. 
The user asked the following search query: {query}
A result was retrieved: {title}
Here is its information: {content}
Describe the result briefly and cheerfully.
Justify the result's relevance briefly."""

# ========== Main Resources ==========

class Recommender:
    """
    A recommender class that abstracts interfacing with Neo4J
    and ChromaDB databases to fetch specimen recommendations.
    """
    def __init__(self):
        self.neo4j_client = GraphDatabase.driver(
            uri=os.getenv('NEO4J_URI'), 
            auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
        )
        self.chromadb_client = chromadb.CloudClient(
            api_key=os.getenv('CHROMA_API_KEY'),
            tenant=os.getenv('CHROMA_TENANT'),
            database=os.getenv('CHROMA_DATABASE')
        )
        self.azure_client  = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
        )
        self.embedding_model = 'text-embedding-3-large'

    def graph_query(self, specimen_name):
        """Queries the Neo4J database to obtain recommendations"""
        with self.neo4j_client.session() as session:
            result = session.run(CYPHER_QUERY, specimen_name=specimen_name)
            recommended_speciments = [record["recommended_name"] for record in result]
        return recommended_speciments
        
    def semantic_query(self, query):
        """Queries the ChromaDB database to obtain similar results"""
        # Step 1. Get the results for the query
        specimens = self.chromadb_client.get_collection('specimens')
        embeddings = self.get_embeddings(text=query)
        results = specimens.query(query_embeddings=embeddings)

        # Step 2. Parse the data and get the top 5
        contents = results['documents'][0][:5]
        metadatas = results['metadatas'][0][:5]

        # Step 3. Generate a descriptor of the results
        general_message = self.describe_results(query, contents)

        # Step 4. List recommendations with additional generated metadata
        recommendations = [] 
              
        for content, metadata in zip(contents, metadatas):
            identifier, title = metadata['specimen_name'], metadata['title']
            description, justification = self.describe_result(query, title, content)
            recommendations.append({
                'identifier': identifier,
                'name': title,
                'description': description,
                'justification': justification
            })

        return general_message, recommendations
    
    def get_embeddings(self, text: str):
        """Gets embeddings from Azure OpenAI"""
        response = self.azure_client.embeddings.create(input=text, model=self.embedding_model, dimensions=1024)
        embeddings = response.data[0].embedding
        return embeddings
    
    def describe_results(self, query, contents):
        """Generates a fun description of search results"""
        retrieval = '\n\n'.join(contents)
        prompt = SUMMARIZE_PROMPT.format(query=query, retrieval=retrieval)
        response = self.azure_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}]
        )
        descriptor = response.choices[0].message.content
        return descriptor

    def describe_result(self, query, title, content):
        """Generates a description and a justification for a result"""
        prompt = RESULT_PROMPT.format(query=query, title=title, content=content)
        response = self.azure_client.chat.completions.create(
            model='gpt-4o-mini',
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': 'Output your JSON result as follows: {"description": your_description, "justification": your_justification}'},
                {'role': 'user', 'content': prompt}
            ]
        )

        result = json.loads(response.choices[0].message.content)
        return result['description'], result['justification']

recommender = Recommender()
app = Flask(__name__)

@app.route('/graph_recommend', methods=['GET'])
def graph_recommend():
    specimen_name = request.args.get('specimen_name')
    if not specimen_name:
        return jsonify({'error': 'No "specimen_name" parameter provided'}), 400
    try:
        recommendations = recommender.graph_query(specimen_name=specimen_name)
        return jsonify({'recommendations': recommendations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/semantic_recommend', methods=['GET'])
def semantic_recommend():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'No "query" parameter provided'}), 400
    try:
        general_message, recommendations = recommender.semantic_query(query=query)
        return jsonify({
            'general_message': general_message,
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
   app.run()
