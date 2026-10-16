#!/usr/bin/env python3
"""Read-only local port adapter: source-bound JSON, nodes, edges, health, SSE."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

CONTENT={'/api/v1/snapshot':'snapshot.json','/api/v1/nodes':'nodes.json',
         '/api/v1/edges':'edges.json','/api/v1/diagnostics':'diagnostics.json',
         '/api/v1/events':'events.ndjson'}
STATIC={'/':'index.html','/index.html':'index.html','/app.js':'app.js',
        '/styles.css':'styles.css'}
MIME={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8',
      '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8',
      '.ndjson':'application/x-ndjson; charset=utf-8'}
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,handler,output,view):
        self.output=Path(output).resolve();self.view=Path(view).resolve()
        super().__init__(address,handler)

class Handler(BaseHTTPRequestHandler):
    server_version='CodePurpleReadOnly/1.0'
    def log_message(self,format,*args):pass
    def send(self,code,body,kind='application/json; charset=utf-8'):
        self.send_response(code);self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'")
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
    def do_HEAD(self):self.do_GET()
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz':
            base=self.server.output
            good=(base/'snapshot.json').is_file() and (base/'manifest.json').is_file()
            data={'service':'codepurple.disjoint_live_census','state':'READY' if good else 'DEGRADED',
                  'port':self.server.server_port,'listener_bind':self.server.server_address[0],
                  'host_exposure':'UNVERIFIED_BY_SERVER_USE_DOCKER_PORT_MAPPING',
                  'read_only':True,'github_mutations_enabled':False,'root_closure_permission':False}
            return self.send(200 if good else 503,(json.dumps(data)+'\n').encode())
        if path=='/metrics':
            try:
                data=json.loads((self.server.output/'snapshot.json').read_text())
                m=data['metrics']
                lines=['# HELP codepurple_census_nodes Observed graph nodes',
                       '# TYPE codepurple_census_nodes gauge',
                       'codepurple_census_nodes '+str(len(data['nodes'])),
                       '# HELP codepurple_census_edges Declared evidence edges',
                       '# TYPE codepurple_census_edges gauge',
                       'codepurple_census_edges '+str(len(data['edges'])),
                       'codepurple_census_repos_observed '+str(m['repos_observed']),
                       'codepurple_census_prs_observed '+str(m['pr_observed']),
                       'codepurple_census_missing_check_vectors '+str(m['pr_status_unmeasured']),
                       'codepurple_admission_hold 1']
                return self.send(200,('\n'.join(lines)+'\n').encode(),'text/plain; version=0.0.4; charset=utf-8')
            except (OSError,ValueError,KeyError):return self.send(503,b'{"error":"metrics unavailable"}\n')
        if path=='/api/v1/stream':
            target=self.server.output/'snapshot.json'
            if not target.is_file():return self.send(503,b'{"error":"no snapshot"}\n')
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache');self.send_header('X-Accel-Buffering','no');self.end_headers()
            try:
                last=''
                for _ in range(5):
                    current=hashlib.sha256(target.read_bytes()).hexdigest()
                    if current!=last:
                        self.wfile.write(('event: census\ndata: '+json.dumps({'digest':current,'authority':'OBSERVATION_ONLY'})+'\n\n').encode());self.wfile.flush();last=current
                    else:
                        self.wfile.write(b': heartbeat\n\n');self.wfile.flush()
                    time.sleep(2)
            except (BrokenPipeError,ConnectionResetError,OSError):pass
            return
        if path in CONTENT:
            target=self.server.output/CONTENT[path]
        elif path in STATIC:
            target=self.server.view/STATIC[path]
        else:
            return self.send(404,b'{"error":"unknown endpoint"}\n')
        try:
            body=target.read_bytes()
            if len(body)>6_000_000:return self.send(413,b'{"error":"asset too large"}\n')
        except OSError:return self.send(503,b'{"error":"source output missing"}\n')
        return self.send(200,body,MIME.get(target.suffix,'application/octet-stream'))

def serve(output,view,host='127.0.0.1',port=8765):
    if not isinstance(port,int) or port<0 or port>65535:raise ValueError('invalid port')
    with Server((host,port),Handler,output,view) as server:
        print('Listening http://'+host+':'+str(server.server_port)+' (READ ONLY)',flush=True)
        server.serve_forever(poll_interval=.1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='output');ap.add_argument('--view',default='view')
    ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8765);a=ap.parse_args()
    serve(a.out,a.view,a.host,a.port)
