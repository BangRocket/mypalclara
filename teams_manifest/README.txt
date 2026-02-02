Teams App Manifest for MyPalClara
==================================

This directory contains the Microsoft Teams app manifest for Clara.

Files:
- manifest.json  - App manifest (requires TEAMS_APP_ID replacement)
- color.png      - 192x192 full color icon
- outline.png    - 32x32 transparent outline icon

Setup Instructions:
-------------------

1. Create Azure Bot Resource:
   - Go to https://portal.azure.com
   - Create resource > "Azure Bot"
   - Note the "Microsoft App ID" (this is your TEAMS_APP_ID)
   - Create a client secret (this is your TEAMS_APP_PASSWORD)

2. Configure the Bot:
   - Set messaging endpoint: https://your-domain.com/api/messages
   - Enable the Microsoft Teams channel

3. Update manifest.json:
   - Replace ${TEAMS_APP_ID} with your actual App ID
   - Update validDomains if hosting on a custom domain

4. Create the App Package:
   zip clara-teams.zip manifest.json color.png outline.png

5. Install in Teams:
   - Teams > Apps > Manage your apps > Upload a custom app
   - Or use Teams Admin Center for organization-wide deployment

Environment Variables:
---------------------
Set these in your .env file or Docker environment:

TEAMS_APP_ID=<your-azure-bot-app-id>
TEAMS_APP_PASSWORD=<your-azure-bot-client-secret>
CLARA_GATEWAY_URL=ws://gateway:18789

Local Development:
-----------------
Use ngrok for local testing:

1. ngrok http 3978
2. Update Azure Bot messaging endpoint to ngrok URL
3. Run: poetry run python -m adapters.teams
