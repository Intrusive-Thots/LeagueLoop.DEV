# LeagueLoop

League of Legends companion client that automates matchmaking and champ-select workflows by talking to the local League Client, with a desktop control panel and optional mobile remote.

## Product surface

**LeagueLoop**:
The full companion product (desktop app + automation + local API + mobile companion).
_Avoid_: LeagueLoop-Lock, the lock, the tool (when you mean the product)

**Desktop App**:
The Windows CustomTkinter control panel the player runs on the same machine as the League Client.
_Avoid_: GUI, window shell, PySide6 shell (architecture docs still mention a Qt migration; the running shell is CustomTkinter)

**Orb**:
The compact, always-on-top mini form of the Desktop App used during draft and in-game so the full window is not required.
_Avoid_: Mini player (UI class name), compact mode (when naming the artifact)

**Mobile Companion**:
The Capacitor/Vite remote UI that controls LeagueLoop through the Local API.
_Avoid_: Android app (when you mean the remote surface generally), LeagueLoopMobile (repo folder name)

**Local API**:
The HTTP control surface LeagueLoop exposes on the desktop machine for the Mobile Companion and other remote clients (default port 8337).
_Avoid_: REST server, backend (when you mean this control port)

## League Client integration

**LCU**:
The local League Client Update HTTP and WebSocket API exposed by the running League Client process (lockfile-authenticated).
_Avoid_: Riot API, game API, client API (when you mean the local client)

**Riot Web API**:
Riot’s public cloud APIs (account, league, match, spectator, etc.), separate from the LCU.
_Avoid_: LCU, web API (without Riot)

**Gameflow Phase**:
The League Client’s current high-level session stage (e.g. Lobby, Matchmaking, ReadyCheck, ChampSelect, InProgress, EndOfGame).
_Avoid_: state (alone), screen, mode (when you mean gameflow)

**Champ Select**:
The draft session where players ban, hover, pick, and lock champions before a match.
_Avoid_: draft (alone — see Draft Assistant), character select

**Ready Check**:
The accept/decline prompt when a match is found.
_Avoid_: queue pop UI, accept dialog

**Matchmaking**:
The phase while the client is searching for a match after queue start.
_Avoid_: queueing (as a phase name)

**In Progress**:
The phase while the match is being played (game process typically alive).
_Avoid_: in-game (as the LCU phase name), live game (when you mean the local phase)

## Automation

**Automation Engine**:
The long-running loop that reacts to Gameflow Phase and LCU events to perform automation actions.
_Avoid_: bot loop, macro engine, AutoLoop (log prefix only)

**Auto-Accept**:
Automatically accepting a Ready Check when a match is found.
_Avoid_: auto queue, instant accept

**Priority Sniper**:
Ordered champion preferences used to pick or swap toward preferred champions during Champ Select.
_Avoid_: pick list, champ priority (when naming the feature)

**ARAM List**:
The player’s ordered ARAM champion priority list used by Priority Sniper in ARAM queues.
_Avoid_: ARAM priorities (as the artifact name)

**Draft Assistant**:
Role-aware hover/ban/pick assistance for draft and ranked queues, including teammate-respect behavior.
_Avoid_: role enforcer (marketing phrase only), auto draft

**Teammate Respect**:
Draft Assistant rule that avoids banning or conflicting with champions teammates are already hovering.
_Avoid_: friendly fire, team polite mode

**Arena Synergy Picker**:
Arena-queue automation for pairing/synergy picks and related bans.
_Avoid_: Arena tool (UI label only), cherry picker

**Auto-Honor**:
Automatically honoring a player after a match (prefer friends, else top performers), with conflict and rate-limit handling.
_Avoid_: honor bot, post-game honor

**Auto-Join**:
Automatically joining a trusted friend’s lobby/party when invited or available.
_Avoid_: VIP lobby inject (implementation phrasing)

**Queue Mode**:
A specific matchmaking queue identified by Riot queue ID (e.g. Draft, Ranked Solo, ARAM, Arena).
_Avoid_: game mode (when you mean queue id), playlist

## Accounts & assets

**Account**:
A stored Riot login identity LeagueLoop can switch into for multi-account workflows.
_Avoid_: profile, user (when you mean a Riot login)

**Summoner**:
The in-client player identity currently signed into the League Client (name, puuid, ranked state, etc.).
_Avoid_: account (when you mean the live client identity)

**DDragon**:
Riot’s static Data Dragon CDN used for champion icons, splash art, and related static assets.
_Avoid_: asset CDN, icon API

**Asset Cache**:
Local on-disk and in-memory storage of DDragon (and related) images used by the Desktop App.
_Avoid_: image folder, icon store

## Cross-cutting internals (product terms)

**Event Bus**:
In-process pub/sub used so UI, Automation Engine, and LCU handlers stay decoupled.
_Avoid_: message queue, signal bus

**App State**:
The in-memory snapshot of connection, phase, lobby, friends, and settings the UI reads after events.
_Avoid_: global state, store (Redux-style)

**Design Tokens**:
Named colors, fonts, radii, and spacing that define the Desktop App visual system.
_Avoid_: theme constants, CSS variables
