"""Print fresh deployment secrets locally; never commits or writes them."""
import secrets,hashlib
if __name__=='__main__':
    password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
    print('Access password (send separately):',password)
    print('DEMO_PASSWORD_VERIFIER='+salt+':'+hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1,dklen=32).hex())
    print('SESSION_SECRET='+secrets.token_urlsafe(48))
    print('BACKEND_API_KEY='+secrets.token_urlsafe(48))
