# LeagueLoop.DEV Troubleshooting & Diagnostics Guide

## Common Issues & Solutions

### 1. League Client Not Detected (`LCU Disconnected`)
- **Symptom**: App status shows `● Disconnected`.
- **Solution**:
  1. Ensure League of Legends client is running.
  2. Click the **🚀 LAUNCH LEAGUE CLIENT** button on the Play page.
  3. Turn ON **Auto-Launch Client on Disconnect** under Settings -> App Preferences.

### 2. Button Handlers Crashing or Showing No Feedback
- **Symptom**: Clicking buttons shows no toast or does nothing.
- **Solution**:
  - `ToastManager.get_instance().show(msg)` handles UI feedback thread-safely. Check `%LOCALAPPDATA%\LeagueLoop\error.log` for any tracebacks.

### 3. Log Directory Location
- Log files are automatically saved at:
  `%LOCALAPPDATA%\LeagueLoop\`
  - `debug.log`: Detailed application and LCU API request logs.
  - `error.log`: Errors and crash tracebacks.
- Click the **📁 OPEN LOGS FOLDER** button on the Dashboard page to open the folder directly in Windows Explorer.
