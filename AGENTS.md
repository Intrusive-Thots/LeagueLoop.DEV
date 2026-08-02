# LeagueLoop Workspace Agent Rules

## Development & Workflow Policies

1. **Target Environment**:
   - All code development, debugging, and refactoring MUST occur within `C:\Users\Malcolm\LeagueLoop.DEV\`.
   - Never edit files in secondary workspace clones (e.g. `didactic-spoon`) or desktop folders unless specifically instructed.

2. **Git Synchronization**:
   - After completing edits or bug fixes, stage modified files and create a clean git commit to keep the repository synced.

3. **Installer Compilation**:
   - Do NOT run `build.bat`, PyInstaller, or any installer compilation commands automatically.
   - Installer builds are strictly triggered on explicit user request.
