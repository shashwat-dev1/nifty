"""Open an existing local terminal, or start it and open after readiness."""
import subprocess,sys,time,webbrowser
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8520'
def ready():
    try:return requests.get(URL+'/api/health',timeout=1).json().get('status')=='ok'
    except Exception:return False
if __name__=='__main__':
    if ready():
        requests.post(URL+'/api/admin/kp/full-day-refresh',json={},timeout=3)
        webbrowser.open(URL);sys.exit(0)
    if not (ROOT/'web/dist/index.html').exists():
        print('Build frontend first: cd web, npm ci, npm run build');sys.exit(1)
    with subprocess.Popen([sys.executable,'-m','uvicorn','custom_api:app','--host','127.0.0.1','--port','8520'],cwd=ROOT) as child:
        for _ in range(100):
            if ready():webbrowser.open(URL);break
            if child.poll() is not None:sys.exit(child.returncode)
            time.sleep(.1)
        print('Local terminal active. Close this window or press Ctrl+C to stop it.')
        try:child.wait()
        except KeyboardInterrupt:child.terminate();child.wait(timeout=5)
