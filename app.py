1import os
2from flask import Flask
3from supabase import create_client, Client
4from dotenv import load_dotenv
5
6load_dotenv()
7
8app = Flask(__name__)
9
10supabase: Client = create_client(
11    os.environ.get("SUPABASE_URL"),
12    os.environ.get("SUPABASE_KEY")
13)
14
15@app.route('/')
16def index():
17    response = supabase.table('todos').select("*").execute()
18    todos = response.data
19
20    html = '<h1>Todos</h1><ul>'
21    for todo in todos:
22        html += f'<li>{todo["name"]}</li>'
23    html += '</ul>'
24
25    return html
26
27if __name__ == '__main__':
28    app.run(debug=True)
