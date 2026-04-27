import sys
import threading
import urllib.request
import urllib.parse
import time

if len(sys.argv) < 2:
    sys.stderr.write("Usage: python sse_proxy.py <SSE_URL>\n")
    sys.exit(1)

SSE_URL = sys.argv[1]
POST_ENDPOINT = None

def sse_listener():
    global POST_ENDPOINT
    req = urllib.request.Request(SSE_URL, headers={'Accept': 'text/event-stream'})
    try:
        response = urllib.request.urlopen(req)
        
        current_event = None
        current_data = []
        
        for raw_line in response:
            line = raw_line.decode('utf-8').strip('\r\n')
            if not line:
                if current_event == "endpoint":
                    endpoint_uri = "".join(current_data)
                    POST_ENDPOINT = urllib.parse.urljoin(SSE_URL, endpoint_uri)
                elif current_event == "message":
                    msg = "".join(current_data)
                    sys.stdout.write(msg + "\n")
                    sys.stdout.flush()
                
                current_event = None
                current_data = []
            elif line.startswith('event:'):
                current_event = line[6:].strip()
            elif line.startswith('data:'):
                current_data.append(line[5:].lstrip()) # lstrip only to remove the space after 'data:'
    except Exception as e:
        sys.stderr.write(f"SSE Error: {e}\n")
        sys.stderr.flush()
        sys.exit(1)

def main():
    global POST_ENDPOINT
    t = threading.Thread(target=sse_listener, daemon=True)
    t.start()
    
    while POST_ENDPOINT is None:
        time.sleep(0.1)
        if not t.is_alive():
            sys.stderr.write("Falha ao conectar no servidor SSE ou obter endpoint.\n")
            sys.exit(1)
            
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = urllib.request.Request(
                POST_ENDPOINT,
                data=line.encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req)
        except Exception as e:
            sys.stderr.write(f"POST Error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
