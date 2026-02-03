# Teams App Package

This directory contains the manifest template for sideloading Clara into Microsoft Teams.

## Setup

1. **Update manifest.json**:
   - Replace `YOUR_APP_ID_HERE` (appears twice) with your Azure Bot App ID
   - Update `developer.name` with your name or organization

2. **Add icons**:
   - `color.png` - 192x192 pixel full-color icon
   - `outline.png` - 32x32 pixel outline icon (transparent background, white outline)

3. **Create the app package**:
   ```bash
   cd adapters/teams/app-package
   zip -r clara-teams.zip manifest.json color.png outline.png
   ```

4. **Sideload into Teams**:
   - Open Microsoft Teams
   - Go to **Apps** → **Manage your apps** → **Upload an app**
   - Select **Upload a custom app**
   - Choose the `clara-teams.zip` file

## Icon Requirements

| Icon | Size | Format | Notes |
|------|------|--------|-------|
| color.png | 192x192 | PNG | Full color, can have transparency |
| outline.png | 32x32 | PNG | White with transparent background |

## Scopes

The bot is configured for:
- `personal` - Direct messages with the bot
- `team` - Channel conversations (mention @Clara)
- `groupChat` - Group chat conversations

## Troubleshooting

If sideloading fails:
1. Ensure your Teams admin has enabled custom app uploads
2. Verify the App ID matches your Azure Bot registration
3. Check that both icon files are included in the zip
