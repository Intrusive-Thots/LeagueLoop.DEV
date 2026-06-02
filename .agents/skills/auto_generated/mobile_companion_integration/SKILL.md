---
name: Mobile Companion Integration
description: Add a new remote control endpoint to local_api.py and wire it into the Capacitor Vite mobile application frontend.
---

# Mobile Companion Integration Workflow

This guide details the process for adding new desktop control and data retrieval features to the Mobile Companion application.

## 1. Exposing API Endpoints in the Python Backend

New features require endpoints in the local API server (`src/services/local_api.py`).

1. **GET Endpoints (Data Retrieval)**:
   Add a conditional block under `do_GET` in `LeagueLoopAPIHandler`:
   ```python
   elif self.path == '/your-endpoint':
       self.send_response(200)
       self._set_cors_headers()
       self.send_header('Content-type', 'application/json')
       self.end_headers()
       
       # Fetch information from the application instance
       app = self.app_instance
       data = {
           "status": "active",
           "payload": getattr(app, "some_attribute", None)
       }
       self.wfile.write(json.dumps(data).encode('utf-8'))
   ```

2. **POST Endpoints (Action Triggering)**:
   Add a conditional block under `do_POST` in `LeagueLoopAPIHandler` for either custom paths or as actions under `/action`:
   ```python
   elif self.path == '/your-action':
       content_length = int(self.headers.get('Content-Length', 0))
       post_data = self.rfile.read(content_length)
       # Parse JSON and invoke background thread or app.after on the main thread
       app = self.app_instance
       if app:
           app.after(0, lambda: app.trigger_action())
           
       self.send_response(200)
       self._set_cors_headers()
       self.send_header('Content-type', 'application/json')
       self.end_headers()
       self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
   ```

## 2. Adding the HTML/CSS UI Elements

1. Edit [index.html](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/LeagueLoopMobile/index.html) to add control elements or modal overlays. Align styles with the dark glassmorphism design system.
2. Edit [style.css](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/LeagueLoopMobile/style.css) for custom selectors, card overlays, and action triggers.

## 3. Wiring Frontend Event Handlers

Edit [main.js](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/LeagueLoopMobile/main.js):
1. Register UI element references at the top under the `UI` state.
2. Implement your fetch or action trigger handlers:
   ```javascript
   async function triggerYourAction() {
       try {
           const res = await fetch(`${baseUrl}/your-action`, {
               method: "POST",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify({ parameter: "value" })
           });
           const data = await res.json();
           addLog(`Action triggered: ${data.status}`);
       } catch (err) {
           addLog(`Action failed: ${err}`);
       }
   }
   ```
3. Bind event listeners inside your script.

## 4. Rebuilding and Compiling the App

Build Vite assets, sync with Capacitor native projects, and compile to APK/AAB:
```powershell
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\LeagueLoopMobile
npm run build
npx cap sync android
cd android
$env:JAVA_HOME = "C:\Program Files\Android\openjdk\jdk-21.0.8"
./gradlew assembleDebug
```
Output apk will land in `LeagueLoopMobile/android/app/build/outputs/apk/debug/app-debug.apk`.
