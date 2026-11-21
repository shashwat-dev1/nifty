from getpass import getpass
from keyring.backends.Windows import WinVaultKeyring
secret=getpass("Paste your Upstox access token (hidden): ").strip()
if not secret:raise SystemExit("No token entered.")
WinVaultKeyring().set_password("NIFTY KP Terminal","Upstox",secret)
print("Saved in Windows Credential Manager. Open Settings and select Test connection.")

