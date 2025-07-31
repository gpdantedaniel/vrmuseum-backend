import os
from flask_cors import CORS
from flask import Flask, redirect, render_template, request, send_from_directory, url_for, jsonify
from neo4j import GraphDatabase

# ========== Neo4J Utilities ==========

# ========== ChromaDB Utilities ==========

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
        self.chromadb_client = None

    def graph_query(self, specimen_name):
        """Queries the Neo4J database to obtain recommendations"""
        with self.neo4j_client.session() as session:
            result = session.run(CYPHER_QUERY, specimen_name=specimen_name)
            return [record["recommended_name"] for record in result]
        
    def semantic_query(self, query):
        """Queries the ChromaDB database to obtain similar results"""
        return # TODO: To be implemented

# Initialize app and recommender
app = Flask(__name__)
CORS(app)
recommender = Recommender()

@app.route('/recommend_by_name', methods=['GET'])
def recommend_by_name():
    specimen_name = request.args.get('specimen_name')
    if not specimen_name:
        return jsonify({'error': 'No query parameter provided'}), 400
    try:
        recommendations = recommender.graph_query(specimen_name=specimen_name)
        return jsonify({'recommendations': recommendations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
   app.run()
