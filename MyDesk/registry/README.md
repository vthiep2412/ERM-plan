# MyDesk Registry Deployment

This is the secure backend for your Hybrid Connection system.

## 1. Prerequisites
- **Vercel Account**: Install CLI `npm i -g vercel` or usage web UI.
- **Firebase Project**: Create one at console.firebase.google.com.
  - Create a **Firestore Database**.
  - Go to Project Settings -> Service Accounts -> **Generate new private key**.
  - Open the downloaded JSON file and copy its ENTIRE content.
- **Python**: Ensure you have Python installed.

## 2. Environment Variables
You must set these in Vercel (Settings -> Environment Variables):

| Name | Value | Description |
|------|-------|-------------|
| `REGISTRY_PASSWORD` | `YOUR_SECRET_PASSWORD` | Master password to view or update links. |
| `FIREBASE_CREDS_JSON` | `{...}` | The **content** of your serviceAccountKey.json (minified). |

## 3. Deploy
Run this in the terminal inside `MyDesk/registry`:
```bash
vercel deploy --prod
```

## 4. Verify
Visit `https://your-project.vercel.app/` and you should see "MyDesk Registry Active (Secure)".
