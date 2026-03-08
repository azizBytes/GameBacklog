# GameBacklog 
soon will transfer to :
# Game Backlog Pro: Architectural Migration

### System Overview
This project is a migration of a monolithic Python/Tkinter application into a **Client-Server** architecture. It uses a **Python (FastAPI)** backend for data orchestration and a **Flutter** frontend for the user interface.

### Important Principles for the AI (Memory)
1. **Zero UI in Python**: All Tkinter, PIL.ImageTk, and messagebox code from the legacy script must be purged. The backend speaks only in JSON.
2. **Object-Oriented Backend**: Logic must be split into `Models`, `Services` (API/DB), and `Controllers` (FastAPI routes). No single-class monoliths.
3. **Hardware Constraints**: The developer is working on a laptop; prioritize lightweight execution and efficient asset loading.
4. **Data Persistence**: The existing `games.db` schema must be respected to ensure no data loss during migration.

### Migration Phases
- **Phase 1 (Sanitize)**: Set up the `/backend` and `/frontend` folders and `.env` security.
- **Phase 2 (Decouple)**: Extract SQLite and RAWG logic into FastAPI endpoints.
- **Phase 3 (Modernize)**: Build a 100% Flutter UI to replace the legacy desktop interface.
- **Phase 4 (Integrate)**: Connect the Flutter app to the FastAPI server and verify DB integrity.

### Tech Stack
- **Backend**: Python 3.10+, FastAPI, SQLite, Pydantic.
- **Frontend**: Flutter (Dart), HTTP, Provider/Riverpod.
- **API**: RAWG Video Games Database API.
