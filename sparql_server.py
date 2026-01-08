from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from rdflib import Graph
import traceback
import os

HTML_INTERFACE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SPARQL Query Interface</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0; }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .content { padding: 30px; }
        label { display: block; font-weight: 600; color: #333; margin-bottom: 10px; font-size: 1.1em; }
        textarea { width: 100%; min-height: 200px; padding: 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 14px; resize: vertical; }
        textarea:focus { outline: none; border-color: #667eea; }
        .controls { display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap; }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
        button:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        .error { background: #fee; border-left: 4px solid #f44336; padding: 15px; border-radius: 6px; color: #c62828; margin-top: 15px; white-space: pre-wrap; font-size: 13px; }
        .success { background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; border-radius: 6px; color: #2e7d32; margin-top: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; text-align: left; font-weight: 600; }
        td { padding: 12px 15px; border-bottom: 1px solid #e0e0e0; }
        tr:hover { background: #f5f5f5; }
        .example-queries { margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px; }
        .example-queries h3 { color: #667eea; margin-bottom: 10px; }
        .example-query { background: white; padding: 10px; margin: 5px 0; border-radius: 4px; cursor: pointer; border: 1px solid #e0e0e0; }
        .example-query:hover { border-color: #667eea; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 SPARQL Query Interface</h1>
            <p>Query loaded: <strong id="tripleCount">Loading...</strong> triples</p>
        </div>
        <div class="content">
            <label for="queryInput">SPARQL Query:</label>
            <textarea id="queryInput">PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?movie ?title
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
}
LIMIT 20</textarea>
            <div class="controls">
                <button onclick="runQuery()">▶ Run Query</button>
                <button onclick="clearResults()">🗑️ Clear</button>
            </div>
            <div class="example-queries">
                <h3>📝 Click to load example:</h3>
                <div class="example-query" onclick="loadExample(0)">Find movies in a country</div>
                <div class="example-query" onclick="loadExample(1)">Find movies directed by a director</div>
                <div class="example-query" onclick="loadExample(2)">Find actors who acted in a movie</div>
                <div class="example-query" onclick="loadExample(3)">Find movies having a actor</div>
                <div class="example-query" onclick="loadExample(4)">Search movies by title keyword</div>
                <div class="example-query" onclick="loadExample(5)">Find country that a movie was made in</div>
            </div>
            <div id="results"></div>
        </div>
    </div>
    <script>
        const examples = [
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?title \n       (SAMPLE(REPLACE(STR(?country), "http://dbpedia.org/resource/", "")) AS ?country)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?director, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?directors)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?actor, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?actors)\n       (SAMPLE(?runtime) AS ?runtime)\n       (SAMPLE(?releaseDate) AS ?releaseDate)\n       (SAMPLE(?imdbId) AS ?imdbId)\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?title .\n  ?movie mc:producedInCountry ?country .\n  OPTIONAL { ?movie mc:hasDirector ?director }\n  OPTIONAL { ?movie mc:hasActor ?actor }\n  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }\n  OPTIONAL { ?movie mc:releaseDate ?releaseDate }\n  OPTIONAL { ?movie mc:imdbId ?imdbId }\n  FILTER(CONTAINS(LCASE(STR(?country)), "united_states"))\n}\nGROUP BY ?movie ?title\nLIMIT 20`,
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?title\n       (SAMPLE(REPLACE(STR(?director), "http://dbpedia.org/resource/", "")) AS ?director)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?actor, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?actors)\n       (SAMPLE(REPLACE(STR(COALESCE(?country, "")), "http://dbpedia.org/resource/", "")) AS ?country)\n       (SAMPLE(?runtime) AS ?runtime)\n       (SAMPLE(?releaseDate) AS ?releaseDate)\n       (SAMPLE(?imdbId) AS ?imdbId)\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?title .\n  ?movie mc:hasDirector ?director .\n  OPTIONAL { ?movie mc:hasActor ?actor }\n  OPTIONAL { ?movie mc:producedInCountry ?country }\n  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }\n  OPTIONAL { ?movie mc:releaseDate ?releaseDate }\n  OPTIONAL { ?movie mc:imdbId ?imdbId }\n  FILTER(CONTAINS(LCASE(STR(?director)), "bob"))\n}\nGROUP BY ?movie ?title\nLIMIT 20`,
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?title\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?actor, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?actors)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?director, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?directors)\n       (SAMPLE(REPLACE(STR(COALESCE(?country, "")), "http://dbpedia.org/resource/", "")) AS ?country)\n       (SAMPLE(?runtime) AS ?runtime)\n       (SAMPLE(?releaseDate) AS ?releaseDate)\n       (SAMPLE(?imdbId) AS ?imdbId)\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?title .\n  OPTIONAL { ?movie mc:hasActor ?actor }\n  OPTIONAL { ?movie mc:hasDirector ?director }\n  OPTIONAL { ?movie mc:producedInCountry ?country }\n  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }\n  OPTIONAL { ?movie mc:releaseDate ?releaseDate }\n  OPTIONAL { ?movie mc:imdbId ?imdbId }\n  FILTER(CONTAINS(LCASE(?title), "robocop"))\n}\nGROUP BY ?movie ?title\nLIMIT 20`,
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?title\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(?actor), "http://dbpedia.org/resource/", ""); separator=", ") AS ?actors)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?director, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?directors)\n       (SAMPLE(REPLACE(STR(COALESCE(?country, "")), "http://dbpedia.org/resource/", "")) AS ?country)\n       (SAMPLE(?runtime) AS ?runtime)\n       (SAMPLE(?releaseDate) AS ?releaseDate)\n       (SAMPLE(?imdbId) AS ?imdbId)\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?title .\n  ?movie mc:hasActor ?actor .\n  OPTIONAL { ?movie mc:hasDirector ?director }\n  OPTIONAL { ?movie mc:producedInCountry ?country }\n  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }\n  OPTIONAL { ?movie mc:releaseDate ?releaseDate }\n  OPTIONAL { ?movie mc:imdbId ?imdbId }\n  FILTER(CONTAINS(LCASE(STR(?actor)), "jackie_chan"))\n}\nGROUP BY ?movie ?title\nLIMIT 20`,
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?title\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?director, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?directors)\n       (GROUP_CONCAT(DISTINCT REPLACE(STR(COALESCE(?actor, "")), "http://dbpedia.org/resource/", ""); separator=", ") AS ?actors)\n       (SAMPLE(REPLACE(STR(COALESCE(?country, "")), "http://dbpedia.org/resource/", "")) AS ?country)\n       (SAMPLE(?runtime) AS ?runtime)\n       (SAMPLE(?releaseDate) AS ?releaseDate)\n       (SAMPLE(?imdbId) AS ?imdbId)\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?title .\n  OPTIONAL { ?movie mc:hasDirector ?director }\n  OPTIONAL { ?movie mc:hasActor ?actor }\n  OPTIONAL { ?movie mc:producedInCountry ?country }\n  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }\n  OPTIONAL { ?movie mc:releaseDate ?releaseDate }\n  OPTIONAL { ?movie mc:imdbId ?imdbId }\n  FILTER(CONTAINS(LCASE(?title), "bob"))\n}\nGROUP BY ?movie ?title\nLIMIT 20`,
            `PREFIX mc: <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?movieTitle\n       (REPLACE(STR(?countryUri), "http://dbpedia.org/resource/", "") AS ?country)\n       ?capital ?population ?areaKm2 ?description\nWHERE {\n  ?movie rdf:type mc:Movie .\n  ?movie mc:title ?movieTitle .\n  ?movie mc:producedInCountry ?countryUri .\n  \n  OPTIONAL {\n    ?factbookCountry owl:sameAs ?countryUri .\n    ?factbookCountry mc:capital ?capital .\n    ?factbookCountry mc:population ?population .\n    ?factbookCountry mc:areaKm2 ?areaKm2 .\n    ?factbookCountry mc:description ?description .\n  }\n  \n  FILTER(CONTAINS(LCASE(?movieTitle), "lorax"))\n}\nLIMIT 20`
        ];
        
        function loadExample(i) { document.getElementById('queryInput').value = examples[i]; }
        
        async function runQuery() {
            const query = document.getElementById('queryInput').value.trim();
            const resultsDiv = document.getElementById('results');
            if (!query) { resultsDiv.innerHTML = '<div class="error">❌ Please enter a query.</div>'; return; }
            resultsDiv.innerHTML = '<div class="success">⏳ Executing query...</div>';
            try {
                const response = await fetch('/sparql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'query=' + encodeURIComponent(query)
                });
                if (!response.ok) throw new Error(await response.text());
                const data = await response.json();
                if (!data.results.bindings.length) {
                    resultsDiv.innerHTML = '<div class="success">✅ Query OK but returned no results.</div>';
                    return;
                }
                let html = `<div class="success">✅ Found ${data.results.bindings.length} result(s)</div><div class="table-wrapper"><table><thead><tr>`;
                data.head.vars.forEach(v => html += `<th>${v}</th>`);
                html += '</tr></thead><tbody>';
                data.results.bindings.forEach(b => {
                    html += '<tr>';
                    data.head.vars.forEach(v => html += `<td>${b[v] ? b[v].value : '-'}</td>`);
                    html += '</tr>';
                });
                html += '</tbody></table></div>';
                resultsDiv.innerHTML = html;
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">❌ Error:\\n${error.message}</div>`;
            }
        }
        function clearResults() { document.getElementById('results').innerHTML = ''; }
        
        // Get triple count
        fetch('/stats').then(r => r.json()).then(data => {
            document.getElementById('tripleCount').textContent = data.triples;
        });
    </script>
</body>
</html>
"""

print("Loading OWL files...")
g = Graph()

owl_files = [
    'factbook_data.owl',
    'movies_from_dbpedia.owl',
    'ontology.owl'
]

for owl_file in owl_files:
    if os.path.exists(owl_file):
        print(f"Loading {owl_file}...")
        try:
            g.parse(owl_file, format='xml')
            print(f"✓ Loaded {owl_file}")
        except Exception as e:
            print(f"✗ Error loading {owl_file}: {e}")

print(f"Total triples loaded: {len(g)}")

class SPARQLHandler(BaseHTTPRequestHandler):
    
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(HTML_INTERFACE.encode('utf-8'))
        elif self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'triples': len(g)}).encode('utf-8'))
        else:
            self.send_error(404, "File not found")
    
    def do_POST(self):
        if self.path == '/sparql':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode('utf-8')
                params = urllib.parse.parse_qs(post_data)
                query = params.get('query', [''])[0]
                
                if not query:
                    self.send_error(400, "No query provided")
                    return
                
                print(f"\n--- Executing query ---\n{query}\n")
                results = g.query(query)
                
                result_data = {
                    "head": {"vars": []},
                    "results": {"bindings": []}
                }
                
                if results:
                    result_list = list(results)
                    if result_list:
                        result_data["head"]["vars"] = [str(var) for var in results.vars]
                        for row in result_list:
                            binding = {}
                            for var in results.vars:
                                value = row[var]
                                if value is not None:
                                    binding[str(var)] = {
                                        "type": "uri" if hasattr(value, 'n3') and value.n3().startswith('<') else "literal",
                                        "value": str(value)
                                    }
                            result_data["results"]["bindings"].append(binding)
                
                print(f"✓ Query returned {len(result_data['results']['bindings'])} results")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(result_data, indent=2).encode('utf-8'))
                
            except Exception as e:
                error_msg = f"Query error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                print(f"✗ {error_msg}")
                
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(error_msg.encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")
    
    def log_message(self, format, *args):
        pass

def run_server(port=8888):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, SPARQLHandler)
    print(f"\n{'='*60}")
    print(f"SPARQL Server running at http://localhost:{port}")
    print(f"{'='*60}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        httpd.shutdown()

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    run_server(port)
